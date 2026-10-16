from pyspark.sql import functions as F, Row
from datetime import datetime
from pyspark.sql.window import Window


dq_results = []

def dq_check(table_name: str, check_name: str, df, condition):
    """Executa uma checagem de qualidade: conta quantas linhas violam a condição esperada."""
    total = df.count()
    failed = df.filter(~condition).count()
    passed = failed == 0
    dq_results.append(
        Row(table_name=table_name, check_name=check_name, total_rows=total,
            failed_rows=failed, passed=passed, checked_at=datetime.now())
    )
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {table_name} | {check_name} | {failed}/{total} linhas falharam")

def dq_check_unique(table_name: str, check_name: str, df, key_cols: list):
    """Checagem de qualidade específica para unicidade de chave."""
    total = df.count()
    dupes = df.groupBy(*key_cols).count().filter("count > 1").count()
    passed = dupes == 0
    dq_results.append(
        Row(table_name=table_name, check_name=check_name, total_rows=total,
            failed_rows=dupes, passed=passed, checked_at=datetime.now())
    )
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {table_name} | {check_name} | {dupes} chaves duplicadas de {total} linhas")