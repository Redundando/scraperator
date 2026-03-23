import boto3

session = boto3.Session()
print(f"Region: {session.region_name}")

ddb = boto3.client("dynamodb")
tables = ddb.list_tables()["TableNames"]
print(f"Tables ({len(tables)}):")
for t in tables:
    print(f"  - {t}")
