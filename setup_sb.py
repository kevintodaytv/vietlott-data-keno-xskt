import httpx
import json

token = "sbp_a76e9460195f103e0ef25648bc46791d08b3814d"
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

print("== CẤY GHÉP SUPABASE CLOUD ==")

# 1. Fetch Orgs
res = httpx.get("https://api.supabase.com/v1/organizations", headers=headers)
if res.status_code != 200:
    print("❌ Lỗi lấy Orgs:", res.status_code, res.text)
    exit(1)
    
orgs = res.json()
if not orgs:
    print("❌ Không tìm thấy Organization nào. Ngài cần vào Dashboard tạo một Org mới!")
    exit(1)

org = orgs[0]
print(f"✅ Found Organization: {org['name']} ({org['id']})")

# 2. Check existing projects
res_proj = httpx.get("https://api.supabase.com/v1/projects", headers=headers)
projects = res_proj.json()
project_name = "Sniper-X-Hub"

project = next((p for p in projects if p["name"] == project_name), None)

if project:
    print(f"⚡ Project {project_name} đã tồn tại! ID: {project['id']}")
else:
    print(f"🚀 Khởi tạo dự án {project_name}...")
    payload = {
        "organization_id": org["id"],
        "name": project_name,
        "region": "ap-southeast-1",
        "plan": "free",
        "db_pass": "AlienNexus@2026_xSkt_SUp3r"
    }
    create_res = httpx.post("https://api.supabase.com/v1/projects", headers=headers, json=payload)
    if create_res.status_code == 201:
        project = create_res.json()
        print(f"✅ Tạo dự án thành công! ID: {project['id']}")
    else:
        print("❌ Lỗi tạo project:", create_res.status_code, create_res.text)
        exit(1)

print("⚡ PROJECT DETAILS ⚡")
print(json.dumps(project, indent=2))

# 3. Lấy API Keys
res_keys = httpx.get(f"https://api.supabase.com/v1/projects/{project['id']}/api-keys", headers=headers)
if res_keys.status_code == 200:
    keys = res_keys.json()
    with open(".env.supabase_keys", "w") as f:
        f.write(json.dumps(keys, indent=2))
    print("✅ Đã xuất API Keys ra file .env.supabase_keys!")
else:
    print("❌ Lỗi lấy keys (Có thể dự án vừa tạo cần vài phút để provision):", res_keys.text)
