# Servidor de preservación de Infinite Crisis: Fases 1 y 2

Este es un servidor nuevo para el cliente de Steam de 2015. Reutiliza todo lo que ya descifró el proyecto
[infinite-crisis-server](https://github.com/EricHardiman/infinite-crisis-server) de EricHardiman: el formato de
los mensajes, los IDs de eventos y los parches del exe. Lo que cambia es la organización, la carga y la
configuración.

Los mensajes que envía son **idénticos byte por byte** a los del servidor anterior.
`tests/test_compat.py` lo comprueba con 26 comparaciones.

## Instalación

1. **Python 3.11 o más nuevo (64 bits)**, y en la consola:
   ```
   pip install pycryptodome
   ```
2. Descomprime esta carpeta **donde quieras**. Ya no hace falta que esté dentro de la carpeta del juego.
3. Copia `config.example.toml` como `config.toml` y cambia `dir` en `[game]` a la carpeta de tu juego
   (la que tiene `InfiniteCrisis.exe` y la carpeta `rp`).
4. **Lista de campeones:** si tu clon del proyecto anterior sigue en `<juego>\_server`, se encuentra sola.
   Si no, copia `champions.json` de ese proyecto a la carpeta `data\`.
5. **Cierra el servidor anterior** (`login_server.py` y `tracer.py`) si está abierto, porque usan los mismos puertos.

## Uso

```
python ic.py doctor     revisa todo y te dice cómo arreglar cada falla
python ic.py patch      crea la llave y el InfiniteCrisis_patched.exe (con la llave correcta)
python ic.py play       arranca el servidor y abre el juego
```

También están `python ic.py server` (solo el servidor, para abrir el juego desde Steam) y
`python ic.py client-args` (muestra los argumentos de inicio del juego).

En el juego: entra con cualquier usuario y contraseña, y luego
**Play Now → VS A.I. → Tutorial → Tutorial 1 → Launch**.

Los registros quedan en `logs\`:

| Archivo | Qué tiene |
|---|---|
| `server.log` | Cada paso de la carga, una línea por paso. Empieza por aquí. |
| `traffic.log` | Todos los mensajes con su volcado hexadecimal. |
| `unhandled.log` | Lo que el juego envía y el servidor todavía no entiende. Aquí aparecen las funciones que faltan. |

## Qué cambió respecto al emulador anterior

| Problema | Causa en el servidor anterior | Ahora |
|---|---|---|
| Desconexiones y reconexiones | Estado global: cada conexión nueva borraba el de la anterior. | Una sesión por conexión. Puedes salir de la partida o cerrar sesión y volver a entrar sin reiniciar el servidor. |
| Desconexión al darle "Launch" dos veces | El segundo clic mandaba una segunda redirección y se cortaba la conexión. | El segundo clic se ignora y queda anotado en el log. |
| Carga que a veces fallaba | Esperas fijas (4 s, 5 s…) sin importar lo que hacía el cliente. | Los objetos se crean cuando el cliente reporta su % de carga (con 10 s como máximo). `server.log` dice cuál de las dos condiciones se cumplió. |
| Temporizadores de una partida que disparaban en la siguiente | Nadie los cancelaba. | Cada partida tiene sus temporizadores y se cancelan todos al salir. |
| El texto del tutorial quedaba cambiado en la segunda partida | Se guardaba en una variable global. | Se guarda por partida. |
| Reenvío completo de objetos cada 2 s | Lo disparaba el silencio de la conexión. | Configurable (`idle_resend`, 5 s por defecto) y solo con el campeón quieto. |
| El login fallaba sin explicación | La llave y el exe parchado no coincidían. | `doctor` lo detecta y `patch` lo corrige. |
| El depurador tumbaba el juego | `restart_test.ps1` siempre conectaba `tracer.py`. | No se usa depurador. |
| Valores escritos dentro del código | Campeón, posición de aparición, tiempos, opciones. | Todo está en `config.toml`. |

## Pruebas que necesito que hagas

Yo no puedo ejecutar el juego. Estas pruebas me dicen si el enfoque funciona.

1. **Tutorial normal.** Juega el Tutorial 1 hasta el segundo punto. ¿Llega igual o más lejos que con el emulador anterior?
2. **Volver a entrar.** Sal de la partida (o cierra el juego) y entra de nuevo sin cerrar el servidor. Antes esto fallaba.
3. **El Batman que se desliza.** En `config.toml` pon `player_class = 0x4000007C` y juega otra vez.
   - Si el segundo Batman desaparece y la cámara te sigue, es la solución.
   - Si la carga se traba, vuelve a `0x40000086` y avísame en qué porcentaje se quedó.
4. **El botón de subir habilidad.** Cuando aparezca, haz clic varias veces. El servidor todavía no lo procesa,
   pero el evento que envía el juego quedará en `logs\unhandled.log`. Con eso puedo programar la respuesta (`SkillRanked`).

Para cada prueba, mándame `logs\server.log`, `logs\unhandled.log` y capturas si algo se ve mal.

## Fase 2: drones y combate básico

Los drones salen ahora de los propios paquetes del juego:

- Las posiciones vienen de los registros de colocación del tutorial (paquete `0xa0000256`). Ahí encontré el grupo
  "03" de la primera zona: el dron de la cinemática, la oleada que llega después, el vehículo y las puertas de drones.
- El modelo de cada dron sale de su variante de personaje (paquete `0xa0000257`). Por ejemplo, "Soldier Drone"
  es `0x40000C72`. Al ser variante, tiene barra de vida y se puede atacar.

Cómo se juega ahora el tutorial:

1. Al terminar la cinemática aparecen el vehículo y las puertas de drones.
2. Las flechas te llevan por dos puntos. Al llegar al segundo aparece **el dron** de la cinemática más
   adelante ("A corrupted drone. Take it out!") y las flechas apuntan hacia él.
3. Clic derecho sobre el dron (o en el suelo junto a él, porque el juego todavía no deja seleccionarlo).
   También sirve A + clic cerca del dron. Batman camina hasta quedar a distancia de golpe y ataca cada segundo.
   La vida del dron baja con cada golpe y, al llegar a 0, el dron muere y desaparece.
4. Llega la oleada: 2 drones cuerpo a cuerpo y 2 a distancia ("More drones are coming!").
5. Al derrotarlos: "Good job!", Batman sube a nivel 2 con un punto de habilidad, y el tutorial pide desbloquear
   la primera habilidad.

Al subir a nivel 2 se muestran la barra de habilidades y sus botones de mejora (son elementos del HUD
propios: Q 30, W 4, E 28, R 5, pasiva 19), con el de Q resaltado.

El objeto "jugador" ahora es `0x4000007C` ("Unnamed Player", sin modelo) para quitar el Batman que se
deslizaba encima del que camina. Si con eso la carga se traba, usa `python ic.py play --clasico`.

Límites de esta fase:

- Los drones todavía no se mueven ni atacan.
- Batman no hace la animación de golpe; solo baja la vida del dron.
- Subir de habilidad sigue sin respuesta. Cuando hagas clic en el botón, el evento quedará en `unhandled.log`
  y con él lo programo.

Los valores del combate (vida del dron, daño, intervalo, alcance) están en `[combat]` en `config.toml`.

Herramientas para explorar los datos:

| Comando | Qué hace |
|---|---|
| `python ic.py layout 0xa0000256` | Lista todo lo colocado en un paquete: nombre, estado de mundo, posición y orientación. |
| `python ic.py variants 0xa0000257` | Lista qué variante con vida corresponde a cada estado de mundo. |
| `python ic.py entities 0x2E000AAB ...` | Busca en TODOS los packs la entidad (0x40...) de cada estado de mundo. Tarda unos minutos; escribe `logs\entidades.txt`. |

## Lo que esta fase NO arregla todavía

La Fase 3: inteligencia artificial de los drones (que se muevan y ataquen), animaciones de ataque, habilidades
(Q/W/E/R y subir de rango), experiencia real, y movimiento sobre la malla de navegación.

## Fase 3: animación de caminar

`diag.py --arreglar` confirmó la causa: el componente de movimiento de Batman tenía la velocidad máxima de la
animación en 0 (los drones tienen 3.0), así que la animación de caminar nunca recibía velocidad. Los drones la sacan
de la propiedad de velocidad de movimiento (`0x100005E4`) de sus datos. Ahora el servidor envía esa propiedad para
Batman (`anim_move_speed` en `[match]`, 4.5 por defecto). No hace falta volver a parchar el exe.

## Fase 3: subir la primera habilidad (temporal)

El cliente todavía no puede avisar al servidor cuando haces clic en el "+" (le falta la lógica de progresión).
Mientras tanto, el servidor desbloquea la primera habilidad solo, 8 segundos después de pedirla, y el tutorial
sigue: se ocultan los botones "+", Superman pide drones de práctica y aparecen 2 para derrotar. Ajustable en
`config.toml`: `[tutorial]  auto_rank_seconds = 8` (0 = desactivado).

Los botones "+" ya no se ocultan al desbloquear la habilidad, porque en el juego desaparecía todo el HUD de
habilidades con ellos. Para volver a ocultarlos: `[tutorial]  hide_upgrade_buttons = true`.

El diagnóstico mostró que al hacer clic en el "+" la interfaz **sí envía `RankSkill`**, aunque la consulta
anterior falle. Solo falta que alguien en el cliente se la pase al servidor (un parche pendiente).

## Fase 3: drones de práctica y cinemáticas

- Los "03ThugA/B" del mapa son matones de Gotham (humanos de la cinemática del dron), no objetivos. Los blancos
  de práctica ahora son **drones de entrenamiento** (`0x40000EB4`, estado de mundo `0x2E000808`, el que tiene la
  habilidad del dron objetivo), en las mismas posiciones.
- Antes de la intro se reproduce la cinemática `0x35000025` (prueba: es la de los núcleos de energía que caen del
  cielo, posiblemente el meteorito). Configurable: `[match]  pre_cinematics = [0x35000025]`, `[]` para quitarla.

Por qué el HUD no muestra la habilidad subida: el aviso `SkillRanked` que la interfaz espera lo envían los scripts
de progresión del juego (`GM_Advancement.RecvNotice_SkillRanked` es una función que llaman esos scripts), y esos
scripts no están en este cliente. Es el mismo hueco que el del "+": hay que reemplazarlos con un parche.

## Fase 3: el inicio del tutorial como en el original (experimento)

Según la descripción del juego original:

- **Vehículo que bloquea la calle:** su registro (`0x2E000AAB`) está en el paquete `0xA000024C`, que ahora se
  carga con la partida (`[match] packs`).
- **Meteoritos:** impactos con el objeto `0x2E0007D4` (lleva la nube de polvo `vfx_env_event_meteor_dust_cloud`).
  El "PowerCore" que probé antes era un relé, no el meteorito. Caen 3 al
  empezar, uno grande detrás de Batman al llegar al primer marcador (con reacción de golpe en Batman) y otro tras el
  primer dron ("Not so fast, Batman"). `[tutorial]  meteors = false` los quita.
- **El humano y el dron peleando:** junto al primer dron aparece el matón (`03ThugB`, no atacable). El dron lo ataca
  cada 1.4 s hasta que Batman ataca; entonces el humano huye y desaparece.
- **La oleada** ahora es de 2 drones cuerpo a cuerpo, que miran al vehículo y lo golpean hasta que Batman los ataca.
- El humano y el dron se miran de frente.
- Al aparecer cada meteorito y el vehículo, el servidor les manda una orden de script de prueba para que
  `diag.py --scripts` escriba sus tablas de scripts (así sé qué orden hace caer el meteorito).
- **Catwoman:** al terminar los drones de práctica se reproduce la cinemática `0x35000034` y, al terminar, el
  vehículo que bloquea la calle desaparece. `catwoman_cinematic = 0` la quita.

## Fase 3: diagnóstico dentro del juego

`tools\diag.py` se conecta al juego con el depurador del proyecto anterior (`tracer.py`) y escribe `logs\diag.log`.

Por qué el "+" no hace nada: el botón pregunta al juego `InqCanRankSkill`. Dentro del exe esa pregunta solo
tiene respuesta si un **script del juego registró un manejador** para ella. Sin manejador, la respuesta lleva un
error y la interfaz nunca envía `RankSkill` (por eso no aparece nada en `unhandled.log`). El diagnóstico anota
qué manejadores registra el juego al cargar la partida y qué responde la consulta.

1. `python ic.py play` y quédate **en el menú**, sin entrar a la partida.
2. En otra consola: `python tools\diag.py --forzar`
3. Juega el Tutorial 1 hasta el "+", haz clic en él 2 o 3 veces y camina un poco.
4. Ctrl+C en la consola del diagnóstico. Manda `logs\diag.log`, `logs\server.log` y `logs\unhandled.log`.

`--packs` anota cada pack de datos (`rp\0x....rp`) que el juego intenta cargar, si falla, y la tabla de
"ranuras" de packs por categoría (el juego reserva un número fijo de ranuras por categoría; sin ranura libre el
pack no se carga y no avisa).

Resultado (2026-10-14): `0xA000009A` y `0xA000024C` son packs de **zona** (categoría `0xd`) y el juego tiene una
sola ranura para esa categoría: si se pide `0xA000009A`, ocupa la ranura, `0xA000024C` (la zona del tutorial) ya no
entra y la carga se traba. No hace falta: todos los registros del vehículo y del meteorito están también en
`0xA000024C` y `0xA0000256`, que sí se cargan.

## Fase 3: props como entidades

El vehículo, las puertas y los meteoritos se creaban con su "estado de mundo" (`0x2E...`) pelado: el objeto existe
(sus scripts arrancan) pero sin modelo. En el juego, un objeto colocable es una **entidad** `0x40...` cuyo gemelo
`0x49...` nombra el estado de mundo en la propiedad `0x510` (por ejemplo la puerta "Door" `0x40000B0F` →
`0x2E0010F3`). Al arrancar, el servidor busca esas entidades en los packs `0xA000024C`, `0xA0000256` y
`0xA0000257` y lo escribe en el log (`props: ...`). `[combat] prop_entities = false` vuelve a lo anterior;
`prop_classes = {"0x2E000AAB" = 0x40000xxx}` fuerza una a mano.

`ic.py entities` (2026-10-14) no encontró entidad para el vehículo ni el meteorito en ningún pack: se crean como
estado de mundo. Lo que sí estaba mal: todas las colocaciones del encuentro usan la **celda 251** del landblock
`0x13cb` y el servidor mandaba celda 0. Ahora los props van con `[combat] scenery_cell = 251`. (Prueba 2026-10-14: sigue sin verse; tampoco era
`DestructiblePriorityLevel` en `UserPreferences.ini`.) `diag.py --colocar` (2026-10-14) mostró la causa:
el cliente **coloca** las puertas (entidad Door `0x40000B0F`, celda 251) pero **nunca** el vehículo ni los meteoritos
(estado de mundo sin entidad: no se crea su componente físico). Ahora esos dos se crean como la entidad Door con la
propiedad `0x510` = su estado de mundo (`[combat] prop_carrier = 0x40000B0F`; 0 = como antes).
Resultado: el vehículo-puerta **sí se colocó** en (43.66, 52.61) pero no se ve (la puerta no tiene modelo y `0x510`
no le cambia el estado de mundo). Ahora `prop_carrier = 0` y los props van como estado de mundo pero **con** módulo
de movimiento `[1, 1]` (`scenery_module`), que es lo que hizo que el cliente colocara la puerta.
Resultado: el estado de mundo del vehículo sigue sin colocarse ni con módulo. Pendiente (análisis del exe): el tipo
de creación de su `.entity` `0x2D0008BC` (`UniqueDynamicImmobile`, `SharedStaticImmobile`...) y si el cliente
solo acepta crearlo desde el mapa.

- **Drones de la oleada:** la capa del encuentro los pone pasado el vehículo (junto a la primera puerta azul); en el
  juego golpean el vehículo desde el lado de Batman. Ahora aparecen a ~3 m del vehículo de ese lado
  (`[tutorial] wave_positions`).

- **Batman flotando:** la altura del clic sube poco a poco (200.0 → 201.7 en la misma calle). Ahora las alturas
  cercanas al suelo se fijan en `[match] ground_z = 200.0` (0 = desactivado).
- **Dos Batman en la cinemática de Catwoman:** la cinemática trae su propio Batman. Antes de empezarla, el servidor
  pone a tu Batman en el mismo lugar y además lo **oculta** con la propiedad `0x90F` (la que usa el reproductor de
cinemáticas del cliente para esconder entidades; la prueba de visibilidad del exe es `0x2A1 && 0x76A && !0x90F`).
Al terminar la cinemática vuelve a mostrarse. `cinematic_hide_champion = false` / `cinematic_place_champion = false`.

`--forzar` hace que la consulta responda "sin error" para ver si el juego llega a enviar `RankSkill` al servidor.
`--arreglar` pone en 7.0 la velocidad máxima de caminar si está en 0. Si con eso Batman camina, la causa queda
confirmada.

## Fase 3: animación de ataque (experimento)

Las animaciones de ataque y de habilidades no las decide el cliente: son **scriptlets** (programas pequeños en los
paquetes, IDs `0x34xxxxxx`) que el servidor ordena ejecutar con el evento `0x8D`. Ya descifré ese evento. Los
scriptlets de Gaslight Batman son estos:

| Scriptlet | Qué es |
|---|---|
| `0x34000037` | Ataque básico (efectos `Vfx_Bmg_Basic_Ranged_Left/Right`) |
| `0x34000038` | Bat Flight (salto / desplazamiento) |
| `0x34000039` | The Bat Scream |
| `0x3400003B` | Sonic Batarang (proyectil) |
| `0x3400003A` | Otra habilidad, sin objetivo |
| `0x34000048` | Pasiva con acumulaciones |

En cada golpe el servidor le ordena a Batman ejecutar un script, y cuando un dron muere, le ordena al dron su
script de muerte. Se configura en `config.toml`:

```
[scripts]
basic_attack_keys = [[0x10000195, 0x10000188], [0x10000196, 0x10000189]]  # animación + efecto del disparo
hit_keys = [0x10000223]      # VFX_CBT_Hit_Shared en el dron golpeado
death_keys = [0x100001FA]    # _Defeat_OnDead al morir el dron
```

Prueba del 2026-10-13: con `Combat_Basic_Attack_Right/Left` el juego acepta la orden (resultado 0) y Batman
mueve los brazos. `CbtState_Death_Induce` no está en la tabla de los drones, por eso ahora la muerte usa
`_Defeat_OnDead`, que sí está.

Segunda prueba: el disparo sale y hace daño, pero va en línea recta y atraviesa al dron; el dron cae de espaldas al
morir. Ahora el servidor le pasa el dron como objetivo al script del disparo (variable `0x108`, la misma que usa
el propio cliente para sus habilidades) y agrega la reacción física al golpe (`0x10000209`). Para quitarlo:
`send_target = false`.

Resultado de la primera prueba (2026-10-13): el juego **sí recibe y entiende** la orden (DID e instancia
correctos), pero la rechaza con `0x80070057`: el scriptlet no está en la tabla de scriptlets que Batman tiene
permitidos. La segunda prueba mostró esa tabla: no contiene IDs `0x34...` sino **nombres de script**
(`0x10000xxx`, por ejemplo `Combat_Basic_Attack_Right`, `Batman_Gaslight_Sonic_Batarang`). Salen de las
tablas de scripts del personaje (propiedad `0x7D2` de su clase → registros `0x1d...`). Por eso la orden ahora
usa esos nombres.

Prueba:

1. `python ic.py play` y quédate en el menú.
2. En otra consola: `python tools\diag.py --scripts`
3. Juega hasta el dron y atácalo.
4. Ctrl+C en el diagnóstico. Mándame `logs\diag.log`, `logs\server.log`, `logs\unhandled.log` y dime si Batman
   hizo la animación de disparo.

En `diag.log`, cada "resultado de la orden" dice qué pasó: `0` = arrancó, `1` = el juego la ignoró,
`0x80070057` = ID no válido, `0x8000ffff` = Batman no tiene componente de scripts.

## Para desarrolladores

- `logs\send.txt`: cada línea `<player|svc|id hex> <evento hex> <cuerpo hex>` se envía al juego en menos de 1 s.
- `python tests/test_e2e.py config.toml`: una partida completa con un cliente simulado. Incluye salir, volver
  a entrar y el doble clic en Launch (89 comprobaciones, incluido el combate). Usa otros puertos en ese config de prueba.
- `python tests/test_compat.py <carpeta _server anterior>`: comparación byte por byte con el servidor anterior.
- `python tests/test_layout.py <carpeta rp>`: comprueba que la tabla del tutorial coincide con los paquetes.

Estructura del código:

| Archivo | Qué hace |
|---|---|
| `icserver/wire.py` | Formato binario. |
| `icserver/messages.py` | Mensajes del protocolo. |
| `icserver/session.py` | Sesiones y secuencia de carga. |
| `icserver/tutorial1.py` | Guion del tutorial. |
| `icserver/server.py` | Puertos y login SOAP. |
| `icserver/doctor.py` | Revisión de la instalación. |
| `icserver/patcher.py` | Parches del exe. |

Infinite Crisis es una marca de Warner Bros. Entertainment / DC Comics. Este proyecto de preservación no
incluye archivos del juego; necesitas tu propia copia de Steam.

## Fase 3: subir la habilidad con el "+" (investigación)

Prueba 2026-10-14: ni el "+", ni Ctrl+Q (`RankUpSkill1` del keymap), ni la Q mandan nada al servidor
(`traffic.log`: solo movimiento, ataque y keepalive). El cliente decide todo eso con los manejadores de
`GM_Advancement` (InqCanRankSkill, RankSkill, InqSkillRank...), que registra un script del juego: el registro
`0x39000001` del pack `0xA0000038` (siempre cargado) usa los nativos de registro `0xE70012`, `0xE70006`,
`0xE70009`. En las partidas no se registra ninguno. Sospecha: el script se activa con el modo "partida iniciada"
(evento `0x2053`), que el servidor no manda porque, enviado con los datos del lobby, cuelga la carga.
Prueba: `[match] send_match_start = "after_intro"` (o `"in_world"`).
Resultado: con los dos el cliente **vuelve a la pantalla de carga** y se conecta al lobby otra vez (`ConnectToLobby
repeated` en `server.log`): `0x2053` es el paso del lobby a la partida y dispara la carga real. Nuevo modo
`send_match_start = "reload"`: el servidor lo manda con los datos del lobby y crea los objetos recién en esa segunda
carga (si no llega en 15 s, los crea igual).

## Fase 3: el "+" llega al servidor (parche del exe)

El "+" de la interfaz sí llama a `GM_Advancement.SendNotice_RankSkill` (nativo rva `0x524500`), pero como ningún
script registra manejador, el clic muere en el cliente. Parche nuevo (`python ic.py patch` lo aplica): la llamada
al despachador (rva `0x5245bf`) pasa por una cueva en relleno `int3` (rva `0x48bc9c`) que primero manda un **ping**
(evento `0x2136`, el mismo de Alt+clic, emisor rva `0x487e60`) con tipo `0x52414E4B` ("KNAR") y luego llama al
despachador original. El servidor reconoce ese ping como "subir habilidad" y desbloquea la Q.
`[tutorial] auto_rank_seconds = 60` queda solo como respaldo.

- **Los drones contraatacan:** el que Batman ataca (y los de la oleada si se acerca a menos de 3 m) camina hacia él,
  lo golpea cada 1.6 s (`Vfx_Min_Basic_Melee`) y le quita 12 de vida (nunca baja de 1). `drones_fight_back = false`.
- **Aparición con teletransporte:** a los drones de la oleada y de práctica se les corre `Vfx_Spawn` +
  `Vfx_Fade_In` al aparecer (`spawn_keys`).

## Fase 3: rangos de habilidad en el HUD, drones de práctica

- **Qué es en realidad el nativo `0x524500`:** es la *consulta de rango* de una habilidad (agente, ranura) que usa
  la interfaz. El HUD la llama para las ranuras 0-5 de golpe cada vez que se refresca (ráfagas de 6 pings en pocos
  ms); al hacer clic en el "+" de la Q la llama sola para la ranura 1. El servidor ahora ignora las ráfagas y solo
  toma como clic una consulta suelta de la ranura 1 (`RANK_BURST_GAP = 0.08 s`). Antes las ráfagas desbloqueaban la
  Q sin que nadie hiciera clic.
- **El HUD muestra el rango:** todas las consultas de rango (la del nativo y la del bucle C++ del HUD, rva
  `0x67c8b1`, que arma `GM_Skill.RecvNotice_UI_SkillUpdate`) pasan por el despachador `0x50e580`, que sin
  manejadores deja todo en rango 0. Dos cuevas nuevas (rva `0x5e7924` y `0x7369d4`, `python ic.py patch`) llaman al
  despachador y, si el agente es el campeón local (rva `0x45d670`) y la ranura es 0-7, leen la propiedad entera
  `0x100006C1` del campeón (lector rva `0x21c990`): 4 bits por ranura, un valor distinto de 0 es el rango. El
  servidor la manda (`Match.skill_ranks`) al subir la Q. **Hay que volver a parchar el exe.**
- **Drones de práctica correctos:** el mundo `0x2E000808` era un drone soldado genérico (mismo rig `0x2D00068A`
  que `0x2E001167`). El drone de práctica es el mundo `0x2E001298` (rig `0x2D000F92`,
  `chr_minion_target_drone`: base con anillo) y su entidad `0x40000BA9`. Posiciones estimadas de la captura
  original (calle arriba, a la izquierda del vehículo); se cambian con `[tutorial] practice_positions`.
  No atacan.
- **Daño de los drones:** 6 por golpe (antes 12).
- **Aparición más lenta:** `[tutorial] spawn_sequence`: `Vfx_Spawn` a 0.1 s, `Vfx_Fade_In` a 0.9 s y a 1.6 s.
- **Animación de ataque:** `Vfx_Min_Basic_Melee` (`0x100000EC`) no mostraba el golpe. Ahora cada golpe usa el
  siguiente guion de `[tutorial] drone_attack_keys` y el log dice cuál fue
  (`hits Batman (attack script 0x...)`): el que se vea bien se deja solo en la lista.
- **Habilidad recomendada (marco naranja + flecha sobre la Q):** la siguiente consulta del bucle del HUD
  (rva `0x67c8c8`, `InqNextRecommendedSkillToRank`) tampoco tiene manejador. Cueva C (rva `0x725a64`) la llama y
  después lee la misma propiedad `0x100006C1`: los 4 bits altos son la ranura recomendada + 1. El servidor marca
  la Q al dar el punto de habilidad y la quita al subirla. Los rangos quedan en las ranuras 0-6.
- **Diagnóstico:** `python tools\diag.py --rangos` anota cada consulta de rango que pasa por las cuevas, si se
  encuentra el campeón y se lee la propiedad, y qué rango / recomendada usa el HUD en cada ranura (y cuándo se
  marca una ranura para refrescar).
- El log ahora dice qué guion de ataque usa cada golpe de los drones (`03MeleeC: attack script 0x... (hit N)`).

## Fase 3: corrección del "+" (diag 2026-10-14)

El diagnóstico `--rangos` mostró qué es cada cosa (los nombres que usaba antes estaban cruzados):

- El nativo rva `0x524500` es la **consulta de rango** (InqSkillRank); Ctrl+Q también la llama. El clic en el "+"
  primero pregunta **InqCanRankSkill** (rva `0x524b00`), que sin manejador responde error `0xe7f` y ahí se corta.
  El **RankSkill** de verdad es el nativo rva `0x524e80` (despachador `0x50e9a0`).
- La propiedad `0x100006C1` sí se lee bien (`leida=1`), pero el bucle C++ del HUD (rva `0x67c640`) **nunca se
  ejecutaba**: solo corre para las ranuras marcadas "sucias", y nada las marcaba.

Parches nuevos (`python ic.py patch`):
- La cueva del ping ahora va en las dos llamadas a RankSkill (el "+" y la tecla de subir la recomendada); el
  servidor recibe el clic real.
- Cueva E: InqCanRankSkill responde "sin error" para la ranura recomendada (la Q en el tutorial), así el clic
  sigue hasta RankSkill.
- Cueva D: antes de cada actualización del HUD lee la propiedad; si cambió, marca las ranuras 0-5 para refrescar
  y el HUD recibe `RecvNotice_UI_SkillUpdate` con rango y recomendada (cuevas A y C).
- `diag.py --rangos` ahora también anota RankSkill, la cueva E y cada refresco de la cueva D.

## Fase 3: el "+" con el mouse y drones menos agresivos

- **El clic en el "+" se cortaba en la consulta de rango:** sin manejador, la consulta devolvía basura (3711 =
  `0xe7f`, el número que se veía sobre la E) y la interfaz no seguía. La cueva B ahora siempre responde el rango
  de la propiedad (0 si no hay). Hay que volver a parchar.
- **Drones:** solo pelea el drone que Batman ataca (antes la oleada entera se activaba al acercarse a 3 m), y si
  Batman se aleja más de 8 m deja de perseguirlo. Mientras no lo ataquen, los de la oleada siguen golpeando el
  vehículo (con el vehículo como objetivo del guion, para que no apunten a Batman).

## Fase 3: ritmo del tutorial como el original

Los tiempos salen del registro de chat de las capturas del original (00:43 "A narrow escape!", 00:46 "We need to
keep moving", 00:55 "What ARE these accursed machines?", 00:58 "A corrupted drone", 01:05 "These metallic monsters",
01:09 "Not so fast / More drones are coming!", 01:12 "Once you start attacking...", 01:22 "Good job!", 01:24, 01:29
"Use a skill point...", 01:36, 01:40 "Construct: target drones?", 01:43 "Practice your new skill"). Antes el
servidor mandaba varios diálogos juntos y se pisaban.

- Cada momento del tutorial es ahora una lista de "golpes" (segundos después del evento, qué): diálogo, pista,
  objetivo, siguiente marcador, o una acción (la oleada aparece con "More drones are coming!", los drones de
  práctica con "Construct: target drones?", el nivel 2 con "Good job!", el botón resaltado con "Use a skill point").
- Al terminar los drones de práctica: "It appears the path forward is blocked." y ~6 s después la cinemática de
  Catwoman.
- Objetivos con el texto del original: "Right-click the drones to defeat them with Basic Attacks (0/2)" (cuenta
  1/2, 2/2), "Click the highlighted button to unlock your Sonic Batarang Skill", "Place your cursor on a target
  and press ('Q') to destroy it with Sonic Batarang".
- `[tutorial] pacing = 1.0` escala todos los tiempos (2 = el doble de lento, 0 = todo junto). Las pruebas usan 0
  (`IC_PACING=1` para probar con los tiempos reales).
- **El humano y el primer dron:** el tutorial reacciona al primer golpe que Batman acierta, no a la orden de
  atacar. El dron sigue peleando con el humano mientras Batman camina hacia él; recién con el primer golpe el dron
  se voltea contra Batman y el humano huye (en la captura del original a las 00:58 se le ve corriendo).

## Fase 3: Sonic Batarang (Q) y drones de práctica

- **Drones amarillos invencibles a ataques básicos:** Batman los golpea (se ve el ataque) pero no les baja vida
  (`[tutorial] practice_immune`).
- **La Q en el servidor:** el cliente manda las órdenes de ataque y de habilidad por el mismo evento `0x20EE`
  (armado en rva `0x670030`): comando 2 (o 9), seguido del número de habilidad (0 = ataque básico) y el objetivo.
  Antes el servidor ignoraba ese número y trataba todo como ataque básico. Ahora una orden con habilidad ≠ 0 es
  la Sonic Batarang: Batman mira al objetivo, corre su guion `Batman_Gaslight_Sonic_Batarang` (`0x10000164`) con el
  objetivo, y el batarang golpea al drone y rebota al más cercano (hasta 2 rebotes, 8 m), 200 de daño a cada uno.
  Al primer uso: "When you use a skill, it goes 'on cooldown'" y luego "...consumed 'Will'".
- **Falta comprobar en el juego** que el cliente mande la orden al apretar Q. `python tools\diag.py --q` anota cada
  orden que arma el cliente, si la rechaza (y en qué chequeo) y si la envía. En `server.log` aparece
  `skill order: command ..., ability ...` cuando llega.

## Fase 3: el rango "de verdad" de las habilidades (la Q)

`diag.py --q` mostró que al apretar Q el cliente ni siquiera arma la orden: la frena antes, porque para él la Q
sigue en rango 0. El rango que usa el propio cliente (función rva `0x463ce0`) no sale de GM_Advancement sino de
una propiedad del campeón: **`0x100000AF`, una lista (tipo `0xC`) de enteros indexada por ranura** (1 = Q). El
servidor nunca la mandaba.

- `wire.py` ahora sabe empaquetar listas (`KIND_ARRAY`: u32 cantidad y, por elemento, id de propiedad empaquetado
  + valor; lector rva `0x101290`).
- Al subir la Q el campeón lleva `0x100000AF = [0, 1, 0, 0, 0, 0]` (`[match] rank_array`). Con eso la Q debería
  verse activa (con color) y poder lanzarse; la orden llega como comando 2 con habilidad ≠ 0 y el servidor hace el
  batarang con rebote.
- `[tutorial] lock_other_skills`: mientras se pide subir la Q se ocultan los "+" de W, E, R y la pasiva.

## Fase 3: "no tengo Will" y el HUD que desaparecía

- **La Q ya se intenta lanzar** (la lista de rangos `0x100000AF` funcionó): el cliente la frena diciendo que no hay
  "Will". El mensaje de vitales `0x42` tiene dos listas y el HUD muestra la suma; el servidor ponía vida y Will en
  la segunda y la primera en ceros. Ahora van en la primera (`[match] vitals_first_list = true`; `false` = como
  antes). El HUD debería verse igual.
- **El HUD desaparecía unos segundos después del "+":** el aviso "Use a skill point..." llegaba 7.5 s después de la
  oleada y, si ya habías subido la Q, igual ocultaba los "+" de W/E/R, y ocultarlos borra todo el HUD de
  habilidades. Ahora ese aviso no sale si la Q ya está subida, y `lock_other_skills` viene apagado.

## Fase 3: la Q funciona (servidor) — animación y tiempos

- Prueba 2026-10-14 10:29: la Q llega (`skill order: command 2, ability 1, target 0x0, position ...`: es un tiro
  hacia el cursor, sin objetivo) y el batarang destruye los dos drones. El cliente repite la orden mientras se
  mantiene Q (4 en medio segundo): ahora hay 2 s de espera entre lanzamientos.
- Animación: Batman corre `Combat_Special_Attack_2` (`0x100000EB`) + `Batman_Gaslight_Sonic_Batarang`
  (`0x10000164`); configurable con `[tutorial] batarang_keys`.
- Tiempos al destruir los drones de práctica: 2 s "When you use a skill, it goes 'on cooldown'", 7 s "...consumed
  'Will'", 12 s "It appears the path forward is blocked.", ~17 s cinemática de Catwoman.

## Fase 3: diálogo repetido, HUD solo con la Q, batarang y drones

- **"It appears the path forward is blocked." salía dos veces:** esa línea pertenece a la propia cinemática de
  Catwoman (en los datos del juego tiene la marca de "línea de cinemática", igual que "No walls can keep me out!").
  El servidor ya no la manda; la cinemática arranca 12 s después del último dron (2 s cooldown, 7 s Will) y ella
  misma dice la línea. `[tutorial] catwoman_delay` para ajustar.
- **Solo la Q en el HUD:** al subir a nivel 2 ya no se restauran los botones de subir de W/E/R/pasiva (quedan
  ocultos, no se ocultan después, que era lo que borraba el HUD). `[tutorial] restore_other_upgrades = true` = como antes.
- **Claves de scripts corregidas:** antes salían de la tabla de nombres equivocada (`0x100000EB` no es
  Combat_Special_Attack_2, es Vfx_Active). Ahora:
  - Batarang: `0x10000164` Batman_Gaslight_Sonic_Batarang + `0x10000171` Vfx_Bmg_Batarang (el proyectil) y
    `0x1000017B` Vfx_Bmg_Batarang_Stop al terminar.
  - Ataque de los drones (uno por golpe, rotando): `0x10000124` Robot_Minion_Melee_Attack + `0x100000EC`
    Vfx_Min_Basic_Melee; `0x10000128` Combat_Basic_Attack + `0x100000EC`; `0x10000124` + `0x10000008`. El log dice
    `attack scripts 0x...+0x... (hit N)`: dime con cuál se ve el golpe y dejo solo esa.
- **Caminar de los drones:** 1.6 m/s (antes 3.0) en pasos cada 0.25 s (antes 0.4 s).
  `[tutorial] drone_walk_speed` y `drone_tick`.

## Fase 3: la cinemática cortaba a Superman

- Prueba 10:55: la cinemática de Catwoman empezó 12.5 s después del último dron, mientras Superman todavía decía
  la línea de "Will". Ahora cada línea espera a que termine la anterior (duración estimada por la longitud del
  texto): 2 s "When you use a skill...", ~10.5 s "Using that skill also consumed 'Will'...", ~19 s cinemática.
  `[tutorial] catwoman_delay = N` fuerza un tiempo fijo (0 = automático).
- La Q es un tiro hacia el cursor: si no hay un dron cerca del punto clicado, ahora golpea al primero que esté en
  la línea del tiro (hasta 12 m). Antes, en la prueba, el primer Q "no encontró objetivo".
- (fase3-av) El cliente **encola** los diálogos: si mandas uno mientras otro suena, espera. Con un batarang rápido,
  "Practice your new skill..." (2 líneas), "When you use a skill..." y "Using that skill..." seguían en cola cuando
  arrancaba la cinemática. Ahora el servidor lleva la cuenta de cuándo termina la cola (duración estimada de cada
  diálogo del tutorial) y la cinemática espera a que se vacíe + 1.5 s.

## Fase 3: vehículo y meteoritos (parche del cliente)

Causa encontrada en el exe: la fábrica de objetos del cliente (`WorldEntityFactory`, rva `0x14f1f0`) solo
construye un objeto a partir de un estado de mundo (`0x2E...`) si ese estado nombra una **entidad padre**. Si no,
escribe "wstate ... is missing a parent .entity" y el objeto nunca se crea. El vehículo (`0x2E000AAB`) y los
meteoritos (`0x2E0007D4`) no tienen padre en los datos (por eso `props: ... (sin entidad)` al arrancar el
servidor). Por eso nunca se colocaron (lo que vio `diag.py --colocar`).

Parche nuevo (rva `0x14f3c2`): en vez de fallar, usa como padre la entidad Puerta `0x40000B0F` (un prop que el
cliente sí coloca) y deja el estado de mundo del prop (modelo y scripts) tal cual. **Hay que volver a parchar el
exe**: `python ic.py patch`.

Posibles efectos: el vehículo podría tener la colisión de la puerta (lo cual nos sirve para bloquear la calle) y
los meteoritos también, eso lo veremos.

Herramientas:
- `python tools\diag.py --entidades` anota cada objeto construido desde un estado de mundo
  (`objeto desde estado de mundo estado=0x2e000aab entidad_padre=0x40000b0f`) y si alguno falla.
- `python ic.py dump` vuelca (en `logs\dump.txt`) los registros del vehículo, del meteorito, de las cinemáticas y
  lo que ellos nombran, buscando en todos los packs. Tarda unos minutos.

### Corrección (fase3-ax)

El diagnóstico de las 11:17 mostró que lo había leído al revés: la fábrica recibe la **entidad** (`0x40...`) y busca
su estado de mundo (Puerta `0x40000B0F` → `0x2E0010F3`, drones `0x40000A5C` → `0x2E000808`). Un estado de mundo
pelado como clase no llega ni a construirse (sin error). El parche de fase3-aw no servía y probablemente rompió la
cinemática de Catwoman (terminó 0.2 s después de empezar): **quitado**.

Parche nuevo: la clase `0x4F` + los 6 dígitos bajos del estado de mundo (vehículo `0x4F000AAB`, meteorito
`0x4F0007D4`) le dice al exe parchado "construye la entidad Puerta pero con este estado de mundo". El servidor ya
manda esas clases (`[combat] prop_override = true`). **Hay que volver a parchar el exe** (`python ic.py patch`).
`diag.py --entidades` ahora anota `PROP 0x4F recibido` y `objeto construido entidad=... estado_de_mundo=...`.

La Q también acierta si el clic queda a 5 m de un dron (antes 4) o en una franja de 2 m de ancho en la línea del tiro.

## Fase 3: el vehículo ya se construye, falla en los componentes (fase3-ay)

Prueba 11:36 con `diag.py --entidades`: la cueva funciona (`PROP 0x4F recibido clase=0x4f000aab` →
`objeto construido entidad=0x40000b0f estado_de_mundo=0x2e000aab`), pero la construcción falla en el **paso 3
(componentes)**: la Puerta no tiene los componentes que pide el estado de mundo del vehículo (el vehículo es de
otro "tipo de creación", propiedad `0x50F` = 5). Lo mismo con los meteoritos. La cinemática volvió a verse.

Siguiente paso, buscar una portadora del mismo tipo:
- `python ic.py carriers` (tarda unos minutos) escribe `logs\portadoras.txt`: entidades cuyo estado de mundo se
  parece al del vehículo (las de puntaje 2-3 arriba). Mándamelo.
- La portadora se elige en `config.toml`: `[combat] prop_carrier_entity = 0x40000xxx` y luego `python ic.py patch`.

Otros cambios:
- La oleada deja el vehículo y va por Batman cuando él se acerca a 6 m o ataca a uno de los dos (los dos juntos).
  `[tutorial] wave_aggro_radius`. El log dice `... leaves the vehicle and goes for Batman`.
- La espera entre el último diálogo y la cinemática de Catwoman es la mitad (`[tutorial] catwoman_wait_scale = 0.5`).

## Fase 3: probar 6 portadoras a la vez (fase3-az)

`portadoras.txt` (11:50): solo una entidad tiene el mismo tipo de creación que el vehículo (`0x50F` = 5):
`0x40000289`, pero está en un pack (`0xA000016B`) que el tutorial no carga. Para no hacer una prueba por candidata,
el exe parchado ahora tiene una **tabla de 6 portadoras**: la clase `0x4A`..`0x4F` + el estado de mundo elige la
portadora 0..5 (`[combat] prop_carriers`, por defecto Puerta `0x40000B0F`, `0x40000289`, `0x400001BD`,
`0x4000081B`, `0x40000B0A`, `0x40000092`; las últimas son entidades de los packs que sí se cargan).
Con `[combat] prop_try_all_carriers = true` el servidor pone el vehículo 6 veces en el mismo sitio, una por
portadora, y los meteoritos van rotando. `diag.py --entidades` muestra cuál se construye sin `paso 3 (componentes)`
(o si la portadora no está cargada: `ERROR: la entidad portadora no está en los packs cargados`).
Hay que volver a parchar: `python ic.py patch`.

La oleada volvió a lo de antes: golpean el vehículo y solo el dron que atacas va por ti.

## Fase 3: por qué los drones seguían "golpeando el vehículo" y qué componente falla (fase3-ba)

- **Drones:** el servidor sí los ponía a pelear contigo, pero al golpear los dejaba mirando al este (un cálculo de
  ángulo con desplazamiento cero daba 0), que es justo hacia el vehículo. Ahora conservan la orientación hacia
  Batman. El log dice `... attacked, turns on Batman`, `... walks to Batman (x m)` y `... hits Batman (x m)`.
- **Vehículo/meteoritos:** la prueba de 11:55 dio el mismo error con las 5 portadoras cargadas (la `0x40000289` no
  está en los packs del tutorial), así que el problema no es la portadora sino algún componente que el estado de
  mundo del vehículo pide. `diag.py --entidades` ahora vigila cada uno de los ~30 creadores de componentes del
  paso 3 y anota solo el que falla: `*** COMPONENTE FALLÓ: creador rva 0x... error 0x...`. No hace falta volver a
  parchar si ya lo hiciste con fase3-az.

## Fase 3: la pieza que fallaba y el inicio con marcadores (fase3-bb)

- **Vehículo/meteoritos:** el diagnóstico de 12:05 marcó siempre el mismo componente (creador rva `0x204760`). Ese
  componente vuelve a leer la clase del objeto desde los datos de creación, donde seguía la clase falsa `0x4A...`
  (la cueva solo la cambiaba en una variable local). Ahora la cueva escribe la portadora también ahí. **Hay que volver
  a parchar** (`python ic.py patch`).
- **Inicio como el original:** al empezar hay un marcador cerca (`[tutorial] walk_targets`, por defecto
  (26.5, 59.8)); al llegar cae el meteorito grande y tumba a Batman; cuando se levanta (`drone_appear_delay` = 6.5 s)
  aparecen el dron y el humano peleando, con un segundo marcador sobre ellos. Al acercarse (≈6 m): "What ARE these
  accursed machines?" / "A corrupted drone. Take it out!". Las claves viejas `targets` y `drone_step` ya no se usan.

## Fase 3: el inicio según el video (fase3-bc)

- Batman no se puede mover hasta que caen los 3 meteoritos pequeños (`[tutorial] start_lock` = 3.5 s) ni mientras
  está en el suelo tras el meteorito grande (`knockdown_lock` = 3 s). El log dice `move order ignored: ...`.
- El segundo marcador (y el dron con el humano peleando) aparece 8.5 s después del golpe, con "You see what Batman
  sees" (`drone_appear_delay`); acercarse antes ya no lo adelanta.
- Marcadores: se mandaban con celda 0; los props que el cliente sí coloca (las puertas) usan la celda 251 del
  encuentro. Ahora los marcadores van con 251 (`[combat] ping_cell`, 0 = como antes).
- Vehículo: el arreglo de fase3-bb no bastó (el mismo componente sigue fallando). `diag.py --entidades` ahora anota
  qué `.entity` resuelve ese componente desde la clase, con qué tipo y qué devuelve.

## Fase 3: marcadores y flechas guía; vehículo con su propio .entity (fase3-bd)

- **Marcadores:** la entidad "Map Ping" (`0x40000A9C`) resultó ser un **InvisibleTarget** (estado `0x2E000002`, el mismo
  que hay en la capa del encuentro sobre el vehículo): no se ve. El marcador del suelo y las flechas a los pies de
  Batman son scripts del propio Batman que están en su tabla: `Vfx_GuideArrow` (`0x10000F80`) y
  `Vfx_GuideArrow_Ping` (`0x10000F86`). Ahora el servidor los lanza sobre Batman apuntando al ping cada vez que
  crea uno (`[tutorial] guide_keys`).
- **Vehículo:** el componente que falla obtiene el `.entity` (modelo/esqueleto `0x2D...`) a partir de la clase; con
  la portadora recibía el de la Puerta junto con el estado de mundo del vehículo. Los objetos del mapa se construyen
  con el estado de mundo ahí, así que la cueva ahora pone el estado de mundo (`0x2E000AAB`). **Volver a parchar.**
  `diag.py --entidades` anota solo para nuestros props: `*** componente 0x204760: clase ... -> .entity ...`, tipo y
  resultado.

## Fase 3: el cliente ya crea el vehículo por su cuenta (fase3-be)

Diag 13:04: a las 13:04:36 (durante la cinemática de entrada) el **propio cliente** construyó el estado de mundo del
vehículo `0x2E000AAB` con su `.entity` `0x2D0008BC`, sin error (tipo 1). O sea, el vehículo existe en el cliente
aunque no se vea; lo que falta es lo que lo muestra/activa. Las 6 portadoras siguen fallando (el componente lee la
clase de otra copia de los datos), así que esa prueba queda apagada (`prop_try_all_carriers = false`).

`diag.py --entidades --colocar --scripts` anota quién crea el vehículo (pila), dónde se coloca y si el cliente acepta
los scripts de las flechas guía (`resultado de la orden`).

## Fase 3: el vehículo bloquea el paso en el servidor (fase3-bf)

Por qué no hay colisiones: el servidor mueve a Batman en **línea recta** hacia el clic (el cliente solo muestra lo que
el servidor manda), así que atraviesa cualquier cosa del mapa: cajas, vehículos, paredes. Las colisiones tienen que
existir en el servidor como obstáculos.

- Primer obstáculo: el vehículo de la calle (`DestVehicle`, centro (43.7, 52.6), girado como en el mapa). Batman se
  detiene al tocarlo en lugar de atravesarlo. Desaparece al terminar la cinemática de Catwoman (el camino se abre).
- `[combat] vehicle_blocks = true` lo activa; `vehicle_box = [4.0, 1.6]` es la mitad del largo y del ancho en metros.
- El log dice `tutorial: the street vehicle blocks the way`.
- Las cajas y demás objetos se pueden agregar igual cuando se conozcan sus posiciones.

## Fase 3: primer obstáculo (cajas) y Batman rodea los obstáculos (fase3-bg)

- **Cajas:** con el recorrido que hiciste rodeándolas (13:29:06–13:29:09) calculé un rectángulo girado
  (centro (32.35, 58.83), mitad 2.53 × 1.89 m, giro 0.30 rad). Va en `[combat] obstacles` como
  `[nombre, x, y, mitad_largo, mitad_ancho, giro]`; se pueden agregar más igual.
- **Rodear:** antes Batman se frenaba en seco al tocar un obstáculo. Ahora, si el clic queda detrás de una caja o del
  vehículo, el servidor busca el camino más corto por las esquinas y Batman lo rodea (como el juego original). Si el
  clic cae dentro de un obstáculo, camina hasta el punto libre más cercano.
- El log dice `tutorial: obstacle Boxes1 at (32.4, 58.8)`.

## Fase 3: carreta + cajas y pared con su forma real (fase3-bh)

- El cliente "pega" cada clic al borde de la zona caminable (por eso se repiten puntos exactos como (28.7, 57.2)).
  Juntando los ~7500 clics de todos los logs sale el mapa de lo caminable, y los huecos son los obstáculos.
- Los obstáculos ahora pueden ser **polígonos** que siguen ese borde: `["Wagon", [[x, y], ...]]` (la carreta y la pila
  de cajas frente a ella, en forma de L) y `["SouthWall", ...]` (la pared/edificio al sur). Un polígono es la línea que
  el centro de Batman no cruza; las cajas sueltas siguen siendo `[nombre, x, y, mitad_largo, mitad_ancho, giro]`.
- Se quitó el rectángulo único `Boxes1` (dejaba pasar por el frente de la carreta y no dejaba acercarse a las cajas).
- Batman rodea los obstáculos por las esquinas (camino más corto) y el camino se recalcula solo cuando cambia el
  clic. Ningún clic registrado cae dentro de un obstáculo.

## Fase 3: cajas del final de la calle, prueba de marcadores y pings Alt/Ctrl (fase3-bi)

- **Obstáculo `Boxes2`:** las cajas y escombros al final de la calle, sacados del borde donde el cliente pega los
  clics ((39.1, 53.0) y (41.1, 49.0)).
- **Marcadores:** el juego tiene un script de guía (`0x1E00055B`: AlertPingScriptlet / AlertArrowScriptlet) que lanza
  `Vfx_GuideArrow_Ping` y `Vfx_GuideArrow` apuntando al ping. No sabemos con qué datos, así que en cada marcador se
  prueban tres formas, una cada 4 s (`[tutorial] guide_variants`, `guide_variant_gap`):
  - **A** (al aparecer): las dos sobre Batman con el ping como variable (como antes).
  - **B** (+4 s): igual que A y además el ping como segundo objeto de la orden.
  - **C** (+8 s): el círculo sobre el ping mismo y las flechas sobre Batman.
  El log dice `tutorial: marker N, guide variant X`.
- **Pings del jugador:** el log ahora dice cuál fue: `ping Alt+click (alert) [type 1]` o
  `ping Ctrl+click (retreat) [type 2]` (antes decía siempre "Alt+click").

## Fase 3: marcador visible, pings Alt/Ctrl corregidos, el marcador se activa al pasar (fase3-bj)

- **Pings del jugador:** salían invertidos. Ahora Alt+clic (alerta) usa la clase `0x4000025B` y Ctrl+clic
  (retirada) la `0x4000025A`.
- **Marcador visible:** como los pings del jugador sí se ven, en cada marcador del tutorial se pone también un ping de
  alerta en el mismo punto, hasta que funcione el círculo original (`[tutorial] marker_ping_class`, 0 = apagado). El
  log dice `tutorial: visible marker N at (x, y)`. Las pruebas A/B/C del círculo siguen corriendo.
- El primer marcador pasa a (25.1, 59.9), donde hiciste el ping (`[tutorial] walk_targets`).
- **Llegar al marcador:** antes había que **detenerse** dentro del radio (3.5 m); ahora basta con pasar por ahí.
  Al caer el meteorito grande Batman se detiene donde esté.

## Fase 3: marcador verde, hay que pararse encima, segundo marcador en el piso, el humano rodea (fase3-bk)

- **Marcador:** ahora es el ping verde (clase `0x4000025A`, `[tutorial] marker_ping_class`).
- **Radio:** hay que pisar el marcador: 1.5 m (`[tutorial] marker_radius`; antes 3.5 m al detenerse y luego al pasar).
- **Segundo marcador:** va en el piso junto a la pelea, en (37.6, 58.0) (`[tutorial] drone_marker`), no debajo del
  dron. "A corrupted drone" sale al pisarlo, y el marcador no se quita hasta que Batman se pare encima (aunque el dron
  ya haya caído).
- **El humano que huye** ahora rodea la carreta y las cajas en vez de atravesarlas (`world.route`). Tarda unos 4 s.

## Fase 3: marcadores en su lugar, pisarlos de verdad, batarang que se detiene (fase3-bl)

- Marcadores donde los marcaste: el primero en (23.6, 60.6) y el segundo en (36.9, 57.6).
- **Pisar el marcador:** caminando por encima cuenta solo a 0.6 m del centro (`marker_pass_radius`); donde Batman se
  detiene cuenta a 1.5 m (`marker_radius`). Así ya no se corta antes de llegar.
- Como el segundo marcador queda a 2 m del dron, el clic en el piso cuenta como atacar al dron solo a 1.6 m
  (`[combat] click_attack_radius`, antes 2.5).
- **Color del marcador:** ahora usa la categoría de nota de mapa que trae el propio ping en los datos del juego (1)
  en vez de 0x12 (`[tutorial] marker_category`). Es la prueba para que salga verde.
- **Disparos del ataque básico:** cada disparo de pistola seguía de largo, atravesaba al dron y desaparecía lejos.
  Ahora, cuando llega al dron (distancia / `[scripts] shot_speed` = 20 m/s), el servidor corta el disparo
  (`Vfx_Bmg_Basic_Stop`) y ahí mismo lanza el impacto (`Vfx_Bmg_Basic_Hit`) y la reacción del dron. El batarang
  quedó como estaba (fase3-bk), que ya se veía bien.
- **Subir de nivel:** ya no se muestra el recordatorio de "gasta tu punto" (elemento 27), el candidato a que todas
  las habilidades se marquen (`[tutorial] skill_point_reminder = true` = como antes).

## Fase 3: edificio del este y prueba del anillo verde (fase3-bn)

- **Obstáculo `EastBuilding`:** el edificio al este de la plaza (borde en x ≈ 45.2 desde y 53.6 hacia el norte),
  sacado de los clics; ya no se puede ir de (45.5, 52.3) a (45.1, 60.3) atravesándolo.
- **Anillo verde (prueba):** el conjunto de propiedades del ping de la guía en los datos (`0x1D0007A9`) trae la
  propiedad `0x8E` con dos efectos (`0x3400053C`, que solo usa ese ping, y `0x34000600`). Ahora se mandan con los
  marcadores (`[tutorial] marker_vfx`, `[]` = apagado).

## Fase 3: el anillo verde cerraba el juego (fase3-bo)

- Diag 15:11 / 15:13: el cliente se caía (acceso inválido en rva `0x561d1`) justo al construir el marcador
  `0x4000025A` con la propiedad `0x8E` (lista de efectos). `marker_vfx` queda apagado (`[]`) por defecto.
- Con `prop_override = false` el vehículo se manda con su estado de mundo `0x2E000AAB` tal cual; la caída ocurrió
  antes de saber si el cliente lo construye. Hay que repetir la corrida con este paquete.

## Fase 3: segundo marcador, bordes del mapa, vehículo y meteoritos SÍ se construyen (fase3-bp)

- **Diag 15:17 (con `prop_override = false`):** el cliente construyó **nuestro** vehículo `0x2E000AAB` (`.entity`
  `0x2D0008BC`, tipo 4, resultado 0) y los meteoritos `0x2E0007D4` (`.entity 0x2D000656`) sin errores, por otro
  camino que el de la cinemática. Con las portadoras fallaba. `prop_override` queda en `false` por defecto (no hace
  falta el parche de portadoras). Falta confirmar si se VEN.
- **El segundo marcador no salía:** al pasar por cualquier lado después del meteorito, el paso del dron se daba por
  cumplido porque su marcador todavía no tenía posición ("sin objetivo = llegó"), y se saltaba también su diálogo.
  Ahora ese paso espera a que el dron aparezca y a que Batman pise el marcador.
- **Bordes del mapa:** los obstáculos eran polígonos finitos y Batman los rodeaba "por fuera del mapa" (se iba
  detrás del edificio para pasar el vehículo). Ahora el edificio del este, la pared norte (`NorthWall`, y = 64.3) y
  el lado sur de la calle (`SouthStreet`) llegan hasta el borde, y un rodeo de más de 2.5 veces la distancia directa
  se descarta: Batman camina recto y se detiene en el obstáculo.

## Fase 3: por qué no se ve el vehículo (diag 15:27) y `diag.py --crear` (fase3-bq)

- El segundo marcador ya sale (log 15:28:13 `visible marker 2`).
- **Vehículo:** con su estado de mundo `0x2E000AAB` el cliente arma TODOS sus componentes sin error (modelo
  `0x2D0008BC`), pero nunca lo coloca en el mapa: en `--colocar` aparecen las puertas en (54.05, 44.80) y
  (89.87, 26.21) con la celda 251 y el marcador en (23.6, 60.6), y nada en (43.66, 52.61). Las puertas se mandan
  como entidad (`0x40000B0F`) y sí se colocan; el vehículo no tiene entidad propia. Lo mismo con los meteoritos.
- En el exe, la creación de objetos (rva `0x14f540`) solo coloca el objeto si trae "posición inicial" (su tercer
  argumento). `python tools\\diag.py --entidades --crear --colocar` anota, para cada objeto, su clase, si trae esa
  posición, el resultado de los componentes y si se le aplicó. Con eso se ve qué le falta al vehículo.

## Fase 3: cueva Z, el vehículo con su modelo sobre la portadora (fase3-br) — VOLVER A PARCHAR

- Diag 15:35 (`--crear`): todos los objetos se crean sin posición inicial y se colocan después con el mensaje
  del servidor. Las puertas (entidad) se colocan; el vehículo y los meteoritos con su estado de mundo pelado arman
  el modelo pero nunca se colocan (los meteoritos se colocan en "ninguna parte", celda `ffffffff`).
- Con portadora (clase `0x4A...`, cueva X) el objeto sí se coloca, pero el componente del modelo (init rva
  `0x1693a0`) buscaba el modelo de la clase `0x4A000AAB` y no lo encontraba. **Cueva Z** (rva `0x2cf73c`, llamada
  desde rva `0x1693aa`): para clases `0x4A`-`0x4F` busca el modelo con `0x2E` + los 24 bits bajos, es decir, el
  modelo del propio vehículo/meteorito. Sin reubicaciones en los bytes tocados.
- `[combat] prop_override` vuelve a `true`. **Hay que volver a parchar:** `python ic.py patch`.

## Fase 3: el vehículo se rompe por pasos (fase3-bs)

- ¡El vehículo ya se ve (cueva Z)! Es un destructible: el juego tiene `Destructible_AdvanceState` (`0x10000063`)
  que lo pasa al siguiente estado (intacto → dañado → destrozado).
- Antes se le mandaba ese script 1 s después de crearlo (prueba vieja); ya no.
- **Batarang al vehículo:** una Q lanzada a menos de 4.5 m del vehículo (sin dron en el camino) lo golpea y avanza un
  estado. El log dice `Sonic Batarang: at the vehicle` y `tutorial: vehicle state N`.
- **Catwoman:** a los `vehicle_break_at` = 6 s de empezar su cinemática se lleva el vehículo hasta destrozado, y al
  terminar la cinemática **ya no se borra**: queda el destrozo (`vehicle_keep_wreck`) y el paso queda libre.
- `[tutorial] vehicle_states`, `vehicle_break_keys`, `vehicle_break_at`, `vehicle_keep_wreck` para ajustar.

## Fase 3: el vehículo no tiene scripts (fase3-bt)

- Diag 15:52 (`--scripts`): al mandarle `Destructible_AdvanceState` al vehículo, el cliente dice "tabla de
  scriptlets: 0 grupos, permitidos: ninguno". El vehículo no acepta scriptlets: romperse no va por ahí. En el exe la
  destrucción es de Havok (`CDestructionComponent`, `hkdDestruction...`), así que falta encontrar qué evento la
  dispara.
- Mientras tanto el vehículo se vuelve a quitar al terminar la cinemática de Catwoman (`vehicle_keep_wreck = false`),
  para que no quede un vehículo entero que se puede atravesar.

## Fase 3: batarang con puntería y el vehículo se va con el golpe de Catwoman (fase3-bu)

- **Batarang:** antes bastaba con que un dron estuviera a 5 m del cursor, aunque Batman lanzara hacia otro lado.
  Ahora solo pega si apuntas encima del dron (1.5 m, `[tutorial] batarang_aim_radius`) o si el dron está en la
  línea del lanzamiento (12 m de largo, 1.5 m de ancho).
- **Vehículo en la cinemática:** a los `vehicle_break_at` = 6 s de empezar la cinemática de Catwoman (cuando lo
  golpea) el vehículo desaparece y el paso se abre. La explosión todavía no: el vehículo no acepta scriptlets y su
  destrucción es de Havok; falta encontrar qué la dispara.

## Fase 3: meteoritos alrededor de Batman y la grieta que se queda (fase3-bv)

- **3 meteoritos pequeños:** ahora caen al lado de Batman al empezar ((20.6, 60.0), (20.8, 57.6), (17.6, 57.2);
  `[tutorial] small_meteors`) y **se quedan** hasta que aparece el siguiente marcador (antes se borraban a los 8 s y
  caían lejos, en (15, 56.5), (24, 66), (30, 55)).
- **Meteorito grande:** cae detrás de Batman en el primer marcador ((19.6, 58.9), `big_meteor`) y se queda (la grieta).
- **Color del marcador (prueba):** los pings llevaban el equipo del campeón (1) y salían rojos. Ahora llevan equipo
  0 (`[tutorial] ping_team`; `-1` = como antes). También vale para tus pings Alt/Ctrl+clic.

## Fase 3: drones que caminan sin saltos, oleada pegada al vehículo, meteoritos apagados (fase3-bw)

- **Drones que "saltaban":** cada actualización mandaba el punto donde el dron estaría 0.25 s DESPUÉS; el cliente
  seguía corriendo desde ahí y luego corregía. Ahora se manda dónde está, con rumbo y velocidad, y después se avanza.
  Además rodean la carreta y las cajas (mismo planificador que Batman).
- **Oleada:** los dos drones salen pegados al costado del vehículo que da a la plaza ((43.6, 55.3) y (41.2, 53.5)).
- **Meteoritos:** el modelo que se carga sale como columnas grises; quedan apagados (`[tutorial] meteor_objects =
  false`). La caída de Batman con el meteorito grande sigue igual.

## Fase 3: caída de Batman con CbtState_KnockUp y diagnóstico de la niebla (fase3-bx)

- **Caída al llegar al primer marcador:** se mandaba `0x10000209` (solo un estremecimiento). Ahora
  `CbtState_KnockUp` (`0x1000003D`, está en la tabla de scripts de Batman) + el efecto de golpe (`0x10000223`):
  lo levanta, cae y se para solo. `[tutorial] knockdown_keys` para probar otras.
- **Color de los pings:** el equipo 0 también salió rojo; `ping_team` vuelve a `-1` (el del campeón).
- **Niebla de guerra / minimapa verde:** el exe tiene `CFogOfWarComponent` (actualización en rva `0x6b3520`), que
  solo trabaja si su dueño tiene posición válida y el estado del juego no es 7. `diag.py --niebla` anota si se
  actualiza y qué la frena. El minimapa verde seguramente es la misma niebla sin calcular.

## Fase 3: tiempos de la caída y niebla de guerra en el servidor (fase3-by)

- **Caída en el primer marcador** (`[tutorial]`): al pisarlo Batman queda quieto; a `knockdown_delay` = 1 s cae el
  meteorito y él se cae; `knockdown_lock` = 7.5 s después de pisar el marcador puede moverse (1 + 5 en el suelo
  + 1.5), y el segundo marcador sale a `drone_appear_delay` = 7 s. "A narrow escape!" a los 6.2 s, el objetivo y la
  pista a los 7 s.
- **Niebla de guerra:** diag 16:38 (`--niebla`): el componente de niebla del cliente SÍ se actualiza (estado 5,
  posición válida). Lo que faltaba es que el servidor no mande lo que Batman no ve. Ahora los personajes (drones,
  el humano, los blancos) que están a más de `vision_radius` = 14 m, o detrás de una pared / la carreta / el vehículo,
  se ocultan con la propiedad `0x90F` y reaparecen al verlos (`fog_of_war`). Los objetos del mapa siguen visibles.

## Fase 3: equipo del jugador (niebla oscura y pings verdes) y drones que revivían (fase3-bz)

- **Equipo en el objeto del jugador:** el cliente tiene modos de niebla por equipo (comandos del teclado
  `SetAllFogOfWarVision`, `SetTeam1FogOfWarVision`, `SetTeam2FogOfWarVision`) y colorea los pings por su equipo
  frente al del jugador. El jugador no tenía equipo: la niebla se veía "todo visible" (clara) y todos los pings
  rojos (enemigo). Ahora el jugador lleva `PVP_Team` = el del campeón (`[match] player_team = false` = como antes).
- **Drones derrotados que volvían a salir:** la niebla del servidor los volvía a mandar al entrar en rango y eso
  los recreaba. Ahora no toca a los muertos ni a los ya quitados (el humano que huye tampoco vuelve).

## fase3-ca — color de los pings

- Los pings y el marcador del tutorial ya no llevan el icono, la categoría ni el
  equipo forzados: solo "mostrar en el mapa". Cada clase usa su propio icono y color
  (Ctrl+clic = retirada 0x4000025A, Alt+clic = alerta 0x4000025B; el marcador del
  tutorial usa la de retirada).
- `[tutorial] ping_style = "minimal"` (por defecto). `"team"` añade PVP_Team y
  `"full"` vuelve al conjunto anterior.

## fase3-cb — color de los pings por tipo, diagnóstico de niebla y minimapa

- El color de un ping lo pone el cliente según la relación entre el equipo del ping y
  el de Batman: mismo equipo = azul, equipo 0 = neutral, otro equipo = rojo. Ahora
  Alt+clic (alerta, 0x4000025B) va con equipo 2 (rojo) y Ctrl+clic (retirada,
  0x4000025A) y el marcador del tutorial con equipo 0 (neutral, debería verse verde).
  Se cambia en `[tutorial] ping_class_teams` (`ping_style = "team"`).
- El minimapa verde es la imagen de relleno: el mapa real solo llega al HUD cuando
  cambia la propiedad 0x100001D3 del jugador, y eso no pasa. `python tools/diag.py
  --minimapa` le pide la imagen al juego dentro de la partida (a los 8 s y a los
  25 s) para confirmar el arreglo antes de parchear el exe.
- `--niebla` ahora también anota el dibujo de la niebla: fuentes de visión, textura,
  si oscurece y qué filtro lo frena.

## fase3-cc — minimapa fijo, pings y Batman en el minimapa

- **Hay que volver a parchear el exe** (`python ic.py patch`). Al cargar el HUD, el
  parche pide la imagen del mapa del Tutorial 1 al administrador del mapa: es lo
  mismo que hizo el diagnóstico `--minimapa` en la prueba de las 17:25, pero sin
  el diagnóstico.
- Cada ping y cada marcador del tutorial llevan una "nota" invisible en el mismo
  punto con el icono del minimapa (0x13000A15, categoría 1). El juego no dibuja en
  el minimapa los objetos de equipo enemigo, por eso la nota va aparte y con
  equipo neutral. Ajustes: `[tutorial] map_notes`, `map_note_icon`,
  `map_note_category`, `map_note_variants` (la variante de icono de cada tipo es
  una suposición).
- Batman lleva "mostrar en el mapa" y el icono de minimapa del avatar del
  tutorial (0x13000376): `[match] champion_map_icon` (0 = no).
- `--niebla` anota además los interruptores de niebla del motor (EnableFog /
  EnableMaskFog) y si el mapa está cargado cuando se dibuja.

## fase3-cd — prueba de la niebla oscura y diagnóstico de las notas del minimapa

- `[match] lighting_env` (antes fijo en 0x10000016): el ambiente de luz de la escena.
  El 2026-10-05 la escena salía casi negra sin él, pero entonces la niebla de guerra
  no tenía ninguna fuente de visión: ese negro pudo ser la niebla misma. Con
  `lighting_env = 0` el servidor no lo manda y el cliente usa el de la región.
- `python tools\diag.py --notas` anota por qué un ping, un marcador o Batman sale o no
  en el minimapa (bandera "mostrar en el mapa", relación de equipo, nota creada).

## fase3-ce — equipo local (diagnóstico)

- El diag `--notas` de las 17:47 mostró por qué nada sale en el minimapa: el juego
  compara el equipo de cada objeto con el equipo LOCAL guardado en el objeto de
  partida ([[0x1777068]+0xbc]) y todo salió "enemigo" (relación 2), incluso Batman
  (equipo 1). Ese equipo local nunca se llena.
- `python tools\diag.py --equipo --notas --niebla` lo escribe (1) a los 3 s, para
  confirmar que con eso salen Batman/pings en el minimapa (y quizá se ilumina la
  zona de visión con `lighting_env = 0`) antes de hacerlo fijo.

## fase3-cf — lectura del equipo en las notas del minimapa

- Diag 17:53: con el equipo local en 1 todo siguió saliendo "enemigo"; antes valía 0
  (no -1). Eso solo pasa si el juego NO logra leer el equipo del propio objeto
  (lectura rva 0x188820, almacén [entidad+0x38]). `--notas` ahora anota esa lectura
  (si la encontró, el tipo y el valor).
- `lighting_env = 0` dejó todo oscuro, también alrededor de Batman: es la luz de la
  escena, no la niebla. Vuelve al valor por defecto (borra la línea).

## fase3-cg — Batman y los pings en el minimapa (parche del exe)

- **Hay que volver a parchear el exe** (`python ic.py patch`).
- Diag 17:57: el lector de notas del minimapa lee el equipo de cada objeto con una
  función (rva 0x188820) que no encuentra las propiedades que manda el servidor
  (al = 0 para todos, Batman incluido): equipo -1 = enemigo = no se dibuja. El parche
  usa en su lugar el lector genérico (rva 0x21c990), el mismo que ya colorea bien
  los pings en el suelo.
- Los pings y el marcador visibles ya no llevan "mostrar en el mapa": la nota la pone
  su compañero invisible (si no, cada ping saldría dos veces).
- fase3-ch: la primera versión del parche llamaba a una dirección equivocada (VA
  0xa1c990 en vez de 0x61c990) y el juego se cerraba al cargar (18:03). Corregido.

## fase3-ci — notas del minimapa: el paso al HUD

- Diag 18:17: con el parche las notas YA se crean (Batman icono 0x13000376
  categoría 2; pings y marcador icono 0x13000A15 categoría 1) y el equipo local en 1
  no cambió nada en pantalla. El juego guarda una sola nota por (categoría, variante):
  cada ping nuevo mueve la anterior.
- `--notas` ahora sigue la nota hasta la interfaz (Flash): si se envía, si la película
  del HUD existe, si encuentra su lista y si llegan las posiciones (UpdateMapNotes).

## fase3-cj — la nota del minimapa la lleva el propio ping

- Diag 18:24: las notas de los compañeros invisibles SÍ llegan al HUD (encuentra su
  lista y las agrega), pero nunca reciben posición (UpdateMapNotes no se llamó ni una
  vez): ese objeto invisible no se coloca en el mundo. Ahora el ping visible y el
  marcador visible llevan su propia nota (icono 0x13000A15, categoría 1, variante por
  tipo). `[tutorial] map_notes = "self"` (o "companion" / "off").
- La nota de Batman se manda al crearlo, durante la carga, cuando el HUD aún no tiene
  su lista de notas (lista = 0): se pierde. Pendiente.

## fase3-cl — minimapa: "mapa entregado"

- **Hay que volver a parchear el exe** (`python ic.py patch`).
- Diag 18:34: el administrador de notas del minimapa corre cada cuadro (rva 0x66a7c0)
  pero nunca llega a poner las posiciones: además del mapa cargado exige la marca
  "mapa entregado al HUD" ([M+0xc8]), que solo pone la re-entrega del HUD cuando el
  mapa ya estaba cargado. La cueva del minimapa ahora también la pone.

## fase3-cm — pings en el minimapa sin el cono amarillo

- 18:41: ¡los pings y Batman ya salen en el minimapa! (con fase3-cl). Pero cada ping
  traía además un cono amarillo: era el icono 0x13000A15 que le mandábamos; el HUD ya
  dibuja el icono del ping por su cuenta. `[tutorial] map_note_icon = 0` (por
  defecto) no lo manda.

## fase3-cn — tiempos en el minimapa

- Pings de jugador: 4.5 s (`[timing] ping_lifetime`, antes 6).
- Marcador del tutorial: sale en el minimapa solo `[tutorial] marker_note_seconds`
  (4 s) desde que aparece; el del suelo sigue hasta que Batman lo pisa. Como el
  cliente solo lee "mostrar en el mapa" al crear un objeto, a los 4 s se crea el mismo
  marcador sin nota (id +8) y se borra el que la tenía.

## fase3-co — marcadores en orden y un solo icono de Batman

- Los marcadores se activan en orden: pasar cerca del dron ya no salta el primer
  marcador (`[tutorial] skip_markers = false`; antes cualquier paso cerca del dron
  hacía aparecer el segundo).
- El minimapa ya dibuja al jugador local por su cuenta (anillo amarillo) desde que el
  administrador de notas funciona; el icono extra 0x13000376 sobraba:
  `[match] champion_map_icon = 0` (por defecto).

## fase3-cq — el marcador del suelo ya no se toca; la nota va aparte

- 19:56: cambiar el marcador por una copia a los 5 s hizo desaparecer el del suelo y
  el icono siguió en el minimapa. Ahora el marcador del suelo no lleva nota y se queda
  hasta que Batman lo pisa; un objeto invisible en el mismo punto lleva el icono del
  minimapa (id marcador + 8) y se borra a los `marker_note_seconds` (5 s).

## fase3-cr — categoría de ping (0x1D) y marcador del suelo de vuelta

- 20:04: sin "mostrar en el mapa" el marcador del suelo no se dibuja (su anillo es
  parte del sistema de notas del mapa), y quitar un objeto no borra su icono del
  minimapa (el juego lo libera 30 s después). El marcador vuelve a llevar su nota.
- Pings y marcador usan ahora la categoría 0x1D (la que el cliente trata como ping de
  jugador, con colores por equipo) en vez de 1, que dibujaba dos iconos. La idea es
  que con ella el minimapa haga la animación del ping y la apague solo.

## fase3-cs — los dos drones del vehículo atacan juntos

- Al atacar uno de los dos drones que golpean el vehículo, el otro también va por
  Batman (antes solo el atacado). La correa de esos dos es 14 m (8 los demás).
- Minimapa: queda como en fase3-cr (un solo ping; el marcador del suelo se apaga con
  el ping, la flecha guía sigue).

## fase3-ct — buscar el meteorito de verdad

- El objeto que usábamos (`0x2E0007D4`, .entity `0x2D000656`) es solo la **nube de
  polvo** del impacto (`vfx_env_event_meteor_dust_cloud_rig`): por eso salían
  "columnas grises" (la malla de la nube sin su animación). El meteorito en sí es otro
  objeto: en `dump.txt` del 14/10 11:26 aparecen `env_event_meteor_a_rig` (la roca con
  su "cap"), `vfx_env_event_meteor_warning` (el aviso en el suelo) y
  `vfx_env_event_meteor_impact` en el pack `0xa000009a`.
- `python ic.py dump <texto> [<texto> ...]` ahora también acepta textos: busca en todos
  los packs, vuelca el registro que contiene cada texto y los registros que lo
  nombran (para llegar al "estado de mundo" 0x2E que hay que crear).

## fase3-cu — el meteorito de verdad

- Del dump de las 20:30: la roca es el estado de mundo `0x2E000BB3` (.entity
  `0x2D00048D`, `env_event_meteor_a_rig`: Root / Meteor / Meteor_cap) y está en el
  pack `0xA000024C`, que el tutorial ya carga (el del vehículo). El `0x2E0007D4` de
  antes era solo la nube de polvo del impacto (las "columnas grises").
- Los meteoritos vuelven a crearse como objetos (`meteor_objects = true`) con la
  roca (`[tutorial] meteor_wstate = 0x2E000BB3`), por el mismo camino que el vehículo
  (clase `0x4A000BB3`, cueva Z para el modelo).
- En el mismo pack hay otros dos candidatos para más adelante: `0x2E0004E5`
  (.entity `0x2D000390`, impacto/aviso) en `0xA000009A`, y la lista del evento
  `0x1D00019C` que nombra aviso, roca e impacto.

## fase3-cv — tamaño de los meteoritos

- 20:42: la roca ya se ve, pero grande. Los meteoritos pequeños llevan ahora la
  propiedad `0x10000426` = 0.5 (`[tutorial] meteor_scale`; el grande
  `big_meteor_scale` = 1.0). Que esa propiedad sea la escala es una suposición: en el
  estado de mundo del avatar del tutorial vale 1.0. `meteor_scale_property = 0` la
  apaga.

## fase3-cw — el cráter del meteorito grande

- Dump 20:54 (`crater`): el cráter es la entidad `0x400004FD` (estado de mundo
  `0x2E0004BE`, .entity `0x2D000375`), con sus registros en packs que el tutorial ya
  carga (`0xA00000B3`, `0xA000024C`). En la lista de colocación de otro tutorial
  (`0x1D0007E9`) aparece como "Crater1/2/3".
- Al llegar al primer marcador ya no cae una roca grande: aparece el cráter en
  (19.6, 58.9) y Batman cae. `[tutorial] big_meteor_crater` (true) y
  `big_meteor_rock` (false). El cráter no se oculta con la niebla.

## fase3-cx — tamaño real de los meteoritos y cráter como prop colocado

- La propiedad `0x10000426` no era la escala. El componente de render
  (VA `0x622F10`) multiplica su escala por la propiedad `0x6B4` (float). El SetScale
  del exe (`0x58D650`) escribe `0x6B4` y el estado de mundo `0x2E001037` la trae
  con 2.1. Ahora los meteoritos pequeños se envían con `0x6B4 = 0.3`. Se configura
  con `[tutorial] meteor_scale`, `big_meteor_scale` y `meteor_scale_property`
  (puede ser una lista).
- El cráter ya no se crea como entidad `0x400004FD`, que no se dibujaba. Ahora se
  crea igual que las rocas que sí se ven: el estado de mundo `0x2E0004BE` mediante
  la clase portadora, en la celda 251. Lo controlan estas claves de `[tutorial]`:
  - `crater_mode` (`wstate` o `entity`);
  - `crater_wstate`, `crater_carrier_slot` y `crater_scale`;
  - `crater_yaw`;
  - `crater_blast`: lanza los scripts de inicio como estallido.
- La entidad `0x400004FD` (modo `entity`) ahora también usa la celda 251.

## fase3-cy — diagnóstico del cráter

- `diag --crear` (21:44): el cráter (`0x4B0004BE`) se construye sin error, igual que
  las rocas. Su `.entity 0x2D000375` sí está en `0xA000024C`, pero es solo un
  esqueleto de un hueso, sin malla, y no termina en una referencia de apariencia
  como el meteorito (`0x19000501`). Lo visible del cráter debe salir de sus
  scripts (VFX y decals).
- Al crearse, el cráter recibe las sondas `[tutorial] crater_keys` (Vfx_Startup,
  Vfx_Spawn_Alt01, Vfx_Event1 y _Entity_OnEnterWorld_Default). `diag --scripts`
  lista su tabla de scriptlets.

## fase3-cz — el cráter usa la portadora 0

- `diag --scripts` (21:52): el cráter se pidió con la clase `0x4B0004BE` (portadora 1,
  entidad `0x40000289`), que no está en los packs cargados. Resultado:
  "BuildCreationInfoFromEntityDesc" falla y el objeto no existe, así que tampoco
  recibe sus scripts. Las rocas usan la portadora 0 (`0x4A...`, la puerta
  `0x40000B0F`), que sí carga. Ahora `crater_carrier_slot = 0`.

## fase3-da — el cráter en su sitio y con su propia entidad (requiere `python ic.py patch`)

- 22:00: el cráter ya se ve, pero quedó unos 6 m a la derecha de donde está en el
  video, y sin la lava. Ahora `BIG_METEOR = (13.5, 60.0)`; se puede ajustar con
  `[tutorial] big_meteor = [x, y, z]`. En pantalla x crece hacia la derecha y y hacia abajo.
- Con la portadora 0 (la puerta) el cráter no tiene scripts: su tabla está vacía
  ("0 grupos"). La lava y el humo deben salir de los scripts de su entidad real,
  `0x400004FD`. Ahora la portadora 1 es `0x400004FD`, y el cráter la usa
  (`crater_carrier_slot = 1`). Como cambió la tabla de portadoras, hay que parchar
  el exe otra vez. Si el diag dice "la entidad portadora no está en los packs
  cargados", se vuelve con `crater_carrier_slot = 0`.

## fase3-db — posición del cráter y propiedades de su plantilla

- 22:14: con la portadora `0x400004FD` el cráter se construye bien, pero esa entidad
  tampoco tiene scriptlets ("0 grupos"). La lava no sale de un script.
- El pack del tutorial (`0xA000024C`) trae la plantilla de aparición del cráter,
  `0x1D0008B6`: entidad `0x400004FD`, estado `0x2E0004BE` y varias propiedades
  (`0x8A5 = 5.0`, `0x8A3 = 3.0`, `0x8B2 = 8`, `0x10000AA7 = 1`, `0x149 = 0x08000000`…).
  Ahora se envían con el cráter (`[tutorial] crater_props`; `[]` = ninguna).
- Posición: en (13.5, 60.0) quedó demasiado a la izquierda. Ahora está en (17.0, 59.5).

## fase3-dc — sin las propiedades de la plantilla

- 22:21: con las propiedades de `0x1D0008B6` el cráter no apareció y los pings del
  jugador dejaron de verse en el minimapa; en el log no aparece ningún ping. Por eso
  vuelven a estar apagadas. `[tutorial] crater_props = "template"` las activa, o se
  puede dar una lista `[id, tipo, valor]`.

## fase3-dd — cráter junto al farol y prueba de lava

- 22:28: el cráter va un poco más cerca del farol (video): ahora está en (15.5, 58.5).
- Posible lava: en la lista de colocación `0x1D0008CC`, junto a los cráteres, está el
  estado `0x2E000A9F`. Su .entity `0x2D0008B6` es una pieza plana de 6 × 6 m
  (0.18 m de alto). Se crea en el mismo punto que el cráter
  (`[tutorial] crater_extras = [[estado, dx, dy], ...]`; `[]` = ninguno).
- Pings en el minimapa: llegan al servidor (22:26), pero no se ven. El lector de
  notas (VA `0xA4B150`) guarda una sola nota por (categoría, variante): si ya
  existe, la reescribe con el objeto nuevo (`0xA144D0`). Los marcadores guía usan la
  misma clave (`0x1D`, variante 0/1) que los pings del jugador. Pendiente:
  `diag --notas`.

## fase3-de — pings del jugador en el minimapa y cráter junto al farol

- `diag --notas` (22:34): las notas de los pings del jugador sí se crean y llegan al HUD
  (categoría `0x1D`), pero no se dibujan. Además comparten la clave
  (categoría, variante) con el marcador guía: un ping de retirada solo reescribía la
  nota del marcador. Los pings se veían con la categoría 1 (fase3-cl/cm) y dejaron de
  verse cuando todo pasó a `0x1D` (fase3-cr). Ahora los pings del jugador usan la
  categoría 1 (`[tutorial] player_note_category`) y el marcador sigue con `0x1D`.
- El extra `0x2E000A9F` era la base de una torreta (no la lava): se quitó
  (`crater_extras = []`). Sirvió para medir la cámara: +x va hacia arriba a la
  derecha en pantalla, +y hacia arriba a la izquierda, a ~53 px por metro. La malla
  del cráter queda corrida ~(3.2, 0.3) m de su origen. Con el farol (~(18.2, 66.0))
  como referencia, el cráter del video tiene el origen en ~(15.7, 60.3).

## fase3-df — pelea dron/humano, iconos de ping y cráter

- Pelea: el diag de las 21:52 muestra que la tabla del dron rechaza `0x10000128` y
  `0x10000008`. Dos de cada tres golpes no hacían nada, de ahí el golpe incompleto.
  Ahora el dron solo usa `0x10000124 + 0x100000EC`. El humano devuelve el golpe medio
  intervalo después (`0x10000124`, `[tutorial] thug_attack_keys`) y el dron reacciona.
- El humano estaba de medio lado: su modelo mira hacia +x con yaw 0 (en el layout,
  -1.529 apunta al dron), y el de los drones hacia +y. Se corrige con
  `[tutorial] thug_yaw_offset` (π/2), que solo cambia hacia dónde mira, no la
  dirección en que se mueve.
- Pings: con categoría 1 y variantes 0/1, los dos tipos salían con el mismo icono.
  Ahora la variante es el tipo de ping del cliente: 1 = alerta, 2 = retirada
  (`[tutorial] player_note_variants`; es una suposición).
- Cráter en (18.0, 61.3).

## fase3-dg — iconos de ping con la categoría del cliente (requiere `python ic.py patch`)

- 23:07: con la categoría 1, la alerta y la retirada salían con el mismo icono. La
  categoría de ping del cliente es `0x1D`: con ella el marcador guía muestra el icono
  verde de retirada. El lector de notas le suma 2 a la variante cuando el ping es del
  equipo 2 (los iconos de enemigo), y el minimapa no los dibuja. Nuestras alertas
  van con el equipo 2 para salir rojas, por eso no aparecían. Parche nuevo: la suma
  pasa a ser + 0 (VA `0xA4B2FC`). Los pings del jugador vuelven a `0x1D` con variante
  0 = alerta y 1 = retirada.
- Humano: con +π/2 quedaba de espaldas al dron; ahora `thug_yaw_offset = -π/2`.
- Primer marcador 1.5 m más adelante: (25.1, 60.3).

## fase3-dh — humano de frente y pings visibles otra vez

- Humano: ya casi de frente; le faltaban ~30°: `thug_yaw_offset = -π/2 + 0.52`.
- Pings: con `0x1D` (y el parche del + 2) no se ven. El icono verde del marcador
  guía en el minimapa no viene de una nota `0x1D`, sino del seguimiento del objetivo
  (el ping guía `0x32`, tipo `0x12`, en el diag de las 22:34). Vuelven a la
  categoría 1, que sí se dibuja, aunque con un solo icono para los dos tipos.
  Falta encontrar el icono de la retirada.

## fase3-di — el icono correcto de cada ping

- La interfaz (Flash, `MapNoteCategoryList` en `tools/gfx/classes_all.txt`) elige el
  icono y la animación del ping por la CATEGORÍA de la nota, no por la variante:
  1 = PING, 17 = ALERT_PING, 18 = ALERT_PING_INGAME, 21 = RETREAT_PING_INGAME,
  22 = RETREAT_PING, 29 (`0x1D`) = BEACON. Ahora la alerta usa 18 y la retirada 21
  (`[tutorial] player_note_categories`). `player_note_category` sigue funcionando y
  fija una sola categoría para los dos.
- Humano: `thug_yaw_offset = -π/2 + 0.35`.
- Inventario de acciones de Batman: `docs/batman_acciones.md` lista las 354 claves de
  su tabla de scriptlets, agrupadas, con el nombre más probable de cada una (hay
  nombres que comparten número). `data/batman_actions.tsv` tiene la misma lista.
- Recorrido de acciones: con `[debug] tour_keys = "all"` (o una lista de claves), al
  empezar el tutorial Batman ejecuta una por una cada `tour_interval` segundos
  (3 s). El `server.log` anota cuál es cada una (`tour N/354: clave nombre`).

## fase3-dj — iconos de ping al derecho, huida del humano y herramienta de habilidades

- Pings: los iconos salían al revés. Ahora alerta = 21 y retirada = 18
  (igual que pasó con las clases de ping).
- Humano: al huir se le quita el giro de la pelea, que era lo que hacía rara la
  carrera (corría de lado). Para la pelea se corre un poco hacia un lado
  (`[tutorial] thug_shift = [0.3, -0.25]` m) sin cambiar hacia dónde mira.
- Paso 2 del plan de Batman: `python tools\habilidades.py ["Gaslight Batman" | 0x48...]`
  escribe `logs\habilidades.txt` con las fichas de habilidades del campeón: textos
  resueltos (nombre y descripción de cada habilidad, con `{}` donde el juego pone el
  número) y cada propiedad con su valor como entero y como float. En el pack
  `0xA0000122`, el registro `0x48000615` trae la pasiva (Echoes), la R (Bat Scream),
  la Q (Sonic Batarang), la W (Sonic Shell) y la E (Bat Flight). Los nombres de las
  propiedades todavía no se conocen.

## fase3-dk — el cráter con lava del mapa

- El volcado de las 23:53 no encuentra ningún "lava" ni "crater" con nombre. El impacto
  del meteorito (`vfx_env_event_meteor_impact_*`) está solo en el pack `0xA000009A`,
  que el tutorial no puede cargar.
- Pero el mapa ya tiene un cráter con lava junto al banco. En el pack de terreno
  `0xA0C112CA` (landblock `0x13cb`), en (38.31, 66.99), hay tres estados de mundo en
  el mismo punto: `0x2E001144`, `0x2E001145` y `0x2E001146` (.entity
  `0x2D000E6B/6C/6D`, en `0xA000024C`, que sí se carga). El 46 lleva una luz cálida.
  Ahora el meteorito grande pone esos tres, en (19.5, 63.0)
  (`[tutorial] lava_crater_at`). `crater_set = "old"` vuelve al cráter `0x2E0004BE`.
- `tools\habilidades.py` no encontró el registro del campeón por su nombre. Para
  Gaslight Batman ahora también lee los registros ya conocidos (`0x48000615`, las
  habilidades, y `0x48000617`, el campeón).

## fase3-dl — el humano vuelve a su postura original y ya no desaparece al huir

- 00:00 (imagen del video): el humano pelea de medio lado frente al dron, así que
  la posición y la orientación originales eran las correctas. `thug_yaw_offset = 0`
  y `thug_shift = [0, 0]`. Se mantiene que devuelva el golpe.
- Al huir desaparecía de golpe: la niebla de guerra lo escondía en cuanto quedaba
  detrás de las cajas o del carro. Al empezar a correr deja de estar sujeto a la
  niebla (se quita igual al llegar).

## fase3-dm — habilidades: textos por tabla

- `habilidades.txt` (00:03) mezclaba descripciones de otros campeones (Catwoman,
  Ivy…): el mismo token de texto se repite en tablas distintas. Ahora los textos se
  buscan por (tabla 0x2B, token).
- Lo que ya se ve: cada habilidad (Echoes, Bat Scream, Sonic Batarang, Sonic Shell,
  Bat Flight) trae su icono (`0x10000302`, una imagen 0x13), su ficha de fórmulas
  (`0x100002a3`, un registro 0x48) y una lista de pares estadística/valor
  (`0x100004b6` = id de la estadística, `0x100004b7` = valor; `0x100004d2` parece el
  valor por rango). Por ejemplo, Sonic Batarang: 25 + 60, ratios 0.7 / 0.6 y las
  estadísticas 18 → 9, 30 → 14, 17 → 4, 22 → 1.25, 15 → 5, 3 y 12. Falta saber qué es
  cada id (enfriamiento, costo, alcance…): se cruzará con los `{}` de las
  descripciones y con lo que muestra el juego.
- Campeón Gaslight Batman: `0x48000617` (pack `0xA00000B8`) → plantilla `0x48000732`.

## fase3-dn — cráter de antes + lava roja encima

- 00:04: el juego del banco (`0x2E001144-46`) tampoco era: sale un hoyo que brilla
  pálido. Se vuelve al cráter que sí se parecía (`0x2E0004BE`, `crater_set = "old"`)
  y encima, en el mismo punto, se pone `0x2E0005D6`: usa la misma entidad del cráter
  (`0x400004FD`), tiene tres mallas y el color `0x2A0 = 0xFF0000FF` (rojo). Debería
  ser la lava. Se cambia con `[tutorial] crater_extras = [[estado, dx, dy], ...]`
  (`[]` = sin lava) y `crater_set = "lava"` vuelve a probar el del banco.

## fase3-do — enfriamiento de la Q en el botón (inicio del motor de habilidades)

- La lava `0x2E0005D6` era un cuadro gris: se quitó (`crater_extras = []`). Lo visual
  del cráter queda para después.
- Evento 0x20F8 del cliente (manejador rva `0x4bc7c0`, lector rva `0x439bd0`): u8 0 |
  u64 agente | u32 ranura | f64 hora de fin. El cliente muestra en el botón el tiempo
  restante (`GM_UI.RecvNotice_StartSkillCooldown`).
- Nuevo `icserver/abilities.py`: el kit de Gaslight Batman por ranura (1 = Q, 2 = W,
  3 = E, 4 = R) con enfriamientos (Q = 9 s por la estadística 18 de Sonic Batarang;
  los demás son provisionales) y el control de enfriamientos. Al lanzar la Q se envía
  el 0x20F8 y no se puede volver a lanzar hasta que termine
  (`[combat] cooldowns = { "1" = 9.0 }`, `enforce_cooldowns`).

## fase3-dp — la Q vuelve a verse lista tras el enfriamiento

- 00:19: el barrido de enfriamiento sí sale, pero al terminar el botón queda gris.
  Al acabar el enfriamiento se manda otro 0x20F8 con 0 s restantes, para que la
  interfaz cierre el reloj (`[combat] cooldown_end_notice`).

## fase3-dq — recorrido corto de acciones

- 00:50: el recorrido completo (354 acciones) es casi todo efectos compartidos por
  todos los campeones (estados, objetos, emotes, cinemáticas): la tabla de Batman
  es la unión de varios grupos. `[debug] tour_keys = "nucleo"` recorre solo 25:
  Q/W/E/R completas, ataque básico, crítico, golpe recibido, lanzado al aire,
  incapacitado, levantarse, muerte, reaparecer, aturdido, nivel, aparecer,
  teletransporte y 4 emotes.

## fase3-dr — botones de habilidad con color (requiere `python ic.py patch`)

- 00:59: el botón de la Q queda siempre opaco. La interfaz habilita un botón
  (`GM_Skill.RecvNotice_EnableSkillButton`, VA `0xa230c0`) solo si no se cumple
  ninguna de sus condiciones de bloqueo. La condición `0x1000003B` (VA `0xa1d3ad`)
  busca la ranura en una lista de "disponibles" que llenaban los scripts del
  servidor original y el nuestro no. Parche: esa condición ya no bloquea (el rango
  0 sigue mostrándose bloqueado aparte).

## fase3-ds — derribo con "incapacitado" y lo que falta del tutorial

- Recorrido corto (01:15): se vieron W, E y R completas; el ataque básico
  (derecha/izquierda) y sus disparos; el crítico; la reacción a golpe;
  `_Defeat_StartupIncapacitated` / `_Defeat_OnIncapacitated`; y `Vfx_Bmg_Spawn`.
  No se vieron: KnockUp, GetUp, muerte, reaparecer, revivir, aturdido, nivel,
  teletransporte ni los emotes.
- Derribo del meteorito: `_Defeat_OnIncapacitated` (`0x100001FB`) y a los
  `[tutorial] knockdown_hold` s (5) `_Defeat_OnRevive` + `RunScript_Vfx_GetUp`
  (`getup_keys`) para que se levante.
- Lo que falta del tutorial 1, según sus conversaciones (después de Catwoman):
  1. Los perseguidores de Catwoman (0x1C9), y con ellos el nivel y desbloquear la W
     (0x1E5, 0x1E4, 0x1C2).
  2. Practicar Sonic Shell (0x1B1, 0x192). Luego "More enemies!" (0x191, 0x199),
     otro nivel y subir una habilidad (0x1D9, 0x1D3), y limpiar drones (0x1CC).
  3. Avanzar (0x38D). Poder robado: cámara de vigilancia (0x22B, 0x22A, 0x196,
     0x1BD, 0x1D2).
  4. Desbloquear la E y practicar Bat Flight (0x1C6, 0x1D1, 0x190, 0x1AA). Más
     drones (0x1AE), subir rango (0x1A1) y la pasiva Echoes (0x18F).
  5. Nivel 6 y desbloquear la R (0x1E2, 0x1CB, 0x1DC). La cámara ve drones lejos
     (0x1A0…0x1B5); desbloquear la cámara y usar Bat Scream (0x1D8, 0x1D0, 0x3AC,
     0x1A5); volver a fijar la cámara (0x1AD, 0x1A8, 0x19F).
  6. Otro coche en el camino: poder robado Superfuerza, lanzar el coche (0x1C5,
     0x1C1, 0x1C0, 0x1B4).
  7. El jefe Destroyer (0x1CF, 0x1D7, 0x1C7) y el final (0x1BC).
