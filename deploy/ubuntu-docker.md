# Ubuntu Docker Deployment

Use these commands on the Ubuntu server.

## 1. Install Docker

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"
```

Log out and log in again after adding your user to the `docker` group.

## 2. Prepare the App

```bash
git clone https://github.com/imam0096361/add-ocr.git
cd add-ocr
cp .env.docker.example .env.local
nano .env.local
```

Put the Gemini key in `.env.local` or `.env`:

```env
GEMINI_API_KEY=your-gemini-api-key-here
```

## 3. Run

```bash
docker compose up -d --build
docker compose logs -f
```

Open:

```text
http://SERVER_IP:8000
```

If the server has UFW enabled:

```bash
sudo ufw allow 8000/tcp
```

## 4. Update Later

```bash
git pull
docker compose up -d --build
```

## 5. Stop

```bash
docker compose down
```

The generated files stay in the Docker volume `add_ocr_data`.
