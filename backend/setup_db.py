import asyncio
import asyncmy

async def setup_user():
    try:
        conn = await asyncmy.connect(host='localhost', port=3306, user='root', password='Msk@2806')
        async with conn.cursor() as cursor:
            # Drop user if exists to start fresh
            await cursor.execute("DROP USER IF EXISTS 'prism_app'@'localhost';")
            # Create user
            await cursor.execute("CREATE USER 'prism_app'@'localhost' IDENTIFIED BY 'rX9kL3pT7vM2qW5nB8cY4dF6hJ1zS0gE';")
            # Grant privileges
            await cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, INDEX ON github_analytics.* TO 'prism_app'@'localhost';")
            # Flush
            await cursor.execute("FLUSH PRIVILEGES;")
            print('Successfully hardened database: created prism_app user with restricted privileges.')
    except Exception as e:
        print(f'Error: {e}')

asyncio.run(setup_user())
