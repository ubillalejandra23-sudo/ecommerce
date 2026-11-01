# Ecommerce Router

Agente de chat para un ecommerce hecho con LangGraph. Un nodo `router` (Claude, con salida estructurada) lee el
mensaje del cliente y lo envía a uno de tres destinos:

- `preventa`: productos, precios, tallas, stock, promociones y pagos antes de comprar.
- `postventa`: reclamos, seguimiento de un pedido, devoluciones, cambios y garantía.
- `generica`: todo lo que no tiene que ver con la tienda, y saludos sin pedido.

Por ahora los agentes destino son cascarones: lo importante es que el enrutamiento sea correcto. La memoria de cada
conversación se guarda por `thread_id` (en la API, el `user_id`).

## Requisitos

- Python 3.12
- Una API key de Anthropic

## Instalación

```
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edita `.env` y completa `ANTHROPIC_API_KEY`. Variables:

| Variable | Para qué |
|---|---|
| `ANTHROPIC_API_KEY` | Clave de la API de Anthropic. |
| `MODELO` | Modelo de Claude a usar (`claude-sonnet-5-5`). |
| `TELEGRAM_TOKEN` | Token que entrega BotFather. Vacío hasta conectar Telegram. |
| `TELEGRAM_SECRET` | Secreto que Telegram envía en cada webhook para que la API lo verifique. |
| `PUBLIC_URL` | URL https pública de la app. Vacía hasta desplegar. |

Nunca subas `.env` al repositorio (está en `.gitignore`).

## Correr el router en local

Desde la raíz del proyecto:

```
python main.py router "mi pedido 4521 llegó roto"
python main.py router "mi pedido 4521 llegó roto" --saltos
python main.py router --diagrama
```

- `--saltos` imprime los nodos por los que pasó el grafo y el motivo.
- `--diagrama` imprime el Mermaid del grafo sin ejecutarlo.

## Levantar la API

```
uvicorn api.app:app --reload --port 8000
```

- Swagger: http://localhost:8000/docs
- Salud: http://localhost:8000/health

Ejemplo (en PowerShell, con tildes, mejor usar el Swagger o Bruno; la consola de Windows no siempre manda UTF-8):

```
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"user_id": "cliente-123", "texto": "quiero devolver unas zapatillas"}'
```

Respuesta:

```json
{"ruta": "postventa", "motivo": "...", "respuesta": "Soy el agente de postventa. ..."}
```

La carpeta `bruno/` es una colección de [Bruno](https://www.usebruno.com/): ábrela y elige el entorno `local` o
`heroku` (la URL base está en la variable `baseUrl`).

## Pruebas

```
pytest tests
python scripts/test_router.py
```

Llaman al modelo real, así que necesitan `ANTHROPIC_API_KEY`. `pytest` exige al menos 13 de 15 aciertos
(el modelo no es determinista); `scripts/test_router.py` muestra la tabla caso por caso.

## Desplegar en Heroku

El proyecto ya incluye `Procfile`, `.python-version` y `requirements.txt`. Mantén `requirements.txt` actualizado
(`pip freeze > requirements.txt`).

```
heroku login
heroku create NOMBRE-DE-TU-APP
heroku config:set ANTHROPIC_API_KEY=tu_clave MODELO=claude-sonnet-5-5 TELEGRAM_SECRET=un_secreto_largo
git push heroku main
heroku open /docs
heroku logs --tail
```

Después de crear la app, guarda su URL en `PUBLIC_URL`:

```
heroku config:set PUBLIC_URL=https://NOMBRE-DE-TU-APP.herokuapp.com
```

## Telegram

El bot usa un webhook y solo `httpx` (sin librerías de bot). `POST /telegram` verifica la cabecera
`X-Telegram-Bot-Api-Secret-Token` (403 si no coincide con `TELEGRAM_SECRET`), ignora updates sin texto, pasa el
mensaje al router con `thread_id = chat_id` y responde con `sendMessage`. A Telegram siempre le contesta 200
enseguida; la respuesta al usuario se envía después.

Antes de empezar: en Telegram habla con [@BotFather](https://t.me/BotFather), ejecuta `/newbot`, copia el token a
`TELEGRAM_TOKEN` en `.env` y elige un `TELEGRAM_SECRET` largo (solo letras, números, `_` y `-`).

1. Variables en Heroku:
   ```
   heroku config:set TELEGRAM_TOKEN=el_token_de_botfather TELEGRAM_SECRET=tu_secreto
   ```
2. Commit y push a GitHub y a Heroku:
   ```
   git add .
   git commit -m "telegram"
   git push origin main
   git push heroku main
   ```
3. Registra el webhook y confirma (con `PUBLIC_URL=https://NOMBRE-DE-TU-APP.herokuapp.com` en tu `.env`):
   ```
   python scripts/set_webhook.py
   python scripts/webhook_info.py
   ```
   `webhook_info.py` debe mostrar `url` terminada en `/telegram`, `updates pendientes: 0` y `último error: ninguno`.
4. Escríbele al bot estos 6 mensajes y mira la ruta de cada uno en los logs
   (`heroku logs --tail`, busca las líneas `telegram chat_id=... ruta=...`):
   - "¿tienen la polera azul en talla M?" → preventa
   - "mi pedido 4521 llegó roto" → postventa
   - "hola" → generica
   - "¿cuánto cuesta el envío a Valparaíso?" → preventa
   - "quiero devolver unas zapatillas" → postventa
   - "¿qué hora es en Tokio?" → generica
5. Si no responde, revisa:
   - El webhook apunta a `https://.../telegram` (https y la ruta `/telegram`): mira `url` en `webhook_info.py`.
   - `TELEGRAM_SECRET` es idéntico en Heroku y en el `.env` con el que corriste `set_webhook.py`.
   - `TELEGRAM_TOKEN` es el correcto (en Heroku, con `heroku config`).
   - `último error` de `webhook_info.py` (un 403 indica secreto distinto) y `heroku logs --tail`.

### Probar antes de desplegar (opcional)

```
uvicorn api.app:app --port 8000
cloudflared tunnel --url http://localhost:8000
```

Pon la URL https que imprime cloudflared como `PUBLIC_URL` en `.env` y corre `python scripts/set_webhook.py`.
Al desplegar en Heroku, vuelve a correrlo con la URL de Heroku.
