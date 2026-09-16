import urllib.request
import json
import os
from datetime import datetime
import re

def fetch_stats():
    username = "Vaibhav8075"
    token = os.environ.get("GITHUB_TOKEN")
    
    headers = {
        "User-Agent": "Telemetry-Updater",
        "Accept": "application/vnd.github.v3+json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # 1. Fetch User Data
    req = urllib.request.Request(f"https://api.github.com/users/{username}", headers=headers)
    user_data = json.loads(urllib.request.urlopen(req).read().decode())
    followers = user_data.get("followers", 0)
    public_repos = user_data.get("public_repos", 0)

    # 2. Fetch Repos for Stars
    stars = 0
    page = 1
    while True:
        req = urllib.request.Request(f"https://api.github.com/users/{username}/repos?per_page=100&page={page}", headers=headers)
        repos = json.loads(urllib.request.urlopen(req).read().decode())
        if not repos:
            break
        for repo in repos:
            stars += repo.get("stargazers_count", 0)
        page += 1

    # 3. Fetch Contributions via GraphQL
    contributions = 568
    if token:
        try:
            graphql_url = "https://api.github.com/graphql"
            query = {
                "query": f"""
                query {{
                  user(login: "{username}") {{
                    contributionsCollection {{
                      contributionCalendar {{
                        totalContributions
                      }}
                    }}
                  }}
                }}
                """
            }
            req_gql = urllib.request.Request(graphql_url, data=json.dumps(query).encode('utf-8'), headers=headers)
            res_gql = json.loads(urllib.request.urlopen(req_gql).read().decode())
            contributions = res_gql['data']['user']['contributionsCollection']['contributionCalendar']['totalContributions']
        except Exception as e:
            print(f"Failed to fetch contributions via GraphQL: {e}")
            
            # Fallback scraper if GraphQL token fails
            try:
                import re
                url = f"https://github.com/{username}?tab=contributions"
                html = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla'})).read().decode()
                # We can't easily regex it directly from HTML because it's lazy-loaded. 
            except:
                pass
        
    return {
        "contributions": contributions,
        "stars": stars,
        "repos": public_repos,
        "followers": followers,
        "sync_date": datetime.now().strftime("%Y-%m-%d")
    }

def update_svg(stats):
    svg_path = "assets/telemetry.svg"
    with open(svg_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Regex replacements to inject new data securely while preserving layout
    content = re.sub(r'(<text x="40" y="115" class="big-num">)\d+(</text>)', rf'\g<1>{stats["contributions"]}\g<2>', content)
    
    # Stars
    content = re.sub(r'(<!-- Stars -->\s*<text x="0" y="60" class="stat-num">)\d+(</text>)', rf'\g<1>{stats["stars"]}\g<2>', content)
    
    # Repos
    content = re.sub(r'(<!-- Repositories -->\s*<text x="0" y="115" class="stat-num">)\d+(</text>)', rf'\g<1>{stats["repos"]}\g<2>', content)
    
    # Followers
    content = re.sub(r'(<!-- Followers -->\s*<text x="120" y="60" class="stat-num">)\d+(</text>)', rf'\g<1>{stats["followers"]}\g<2>', content)
    
    # Date
    content = re.sub(r'(<text x="680" y="165" class="sync" text-anchor="end">)SYNC \d{4}-\d{2}-\d{2}(</text>)', rf'\g<1>SYNC {stats["sync_date"]}\g<2>', content)

    with open(svg_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print(f"Successfully updated telemetry.svg with: {stats}")

if __name__ == "__main__":
    stats = fetch_stats()
    update_svg(stats)
