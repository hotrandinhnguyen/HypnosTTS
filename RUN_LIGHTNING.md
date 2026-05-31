# Run with Lightning

## 1. Lightning

On Lightning:

```bash
cd /teamspace/studios/this_studio
python lightning_imgserver/image_server.py
```

Check on Lightning:

```bash
curl http://localhost:8001/health
```

Current intended I2V settings:

```text
auto images: about 1 image / 5 seconds
I2V frames: 49 frames / clip
I2V size: 768x432, with lower fallback on OOM
```

Sync server changes to Lightning:

```powershell
scp .\lightning_imgserver\image_server.py s_01ks9n5bq8xb18g482maabnrbe@ssh.lightning.ai:/teamspace/studios/this_studio/lightning_imgserver/image_server.py
```

After sync, restart the Lightning command above. Health should show `i2v_size":"768x432"`.

## 2. Windows Tunnel

If SSH is not set up yet:

```powershell
iwr "https://lightning.ai/setup/ssh-windows?t=47a21f0c-3b47-4927-bfe8-02efc8e47635&s=01ks9n5bq8xb18g482maabnrbe" -useb | iex
```

Open the tunnel:

```powershell
ssh -i $env:USERPROFILE\.ssh\lightning_rsa -L 8001:localhost:8001 s_01ks9n5bq8xb18g482maabnrbe@ssh.lightning.ai
```

Keep this terminal open.

Test from another PowerShell:

```powershell
Invoke-WebRequest http://localhost:8001/health -UseBasicParsing
```

## 3. Local Backend

From repo root:

```powershell
cd D:\HypnosTTS
.\.venv\Scripts\activate
python run_app.py
```

## 4. Local Frontend

In another PowerShell:

```powershell
cd D:\HypnosTTS\app\frontend
npm run dev
```

Open:

```text
http://localhost:5173
```

## Required `.env`

```env
IMAGE_PROVIDER=remote
IMAGE_API_URL=http://localhost:8001
```
