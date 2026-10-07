# usando lib para nao ter que ficar instanciando em todos os notebooks assim melhora o caso de uso caso futuramente tenhamos que mudar de path 
# usando para lidar com a api pois caso tenhamos que trocar o link por problemas evitamos de mudar manualmente e deixamos o codigo melhor indentado 

import requests
from pyspark.sql import functions as F

catalog = "medalhao_cinema"

bronze_schema = f"{catalog}.bronze"
silver_schema = f"{catalog}.silver"
gold_schema = f"{catalog}.gold"

landing_path = "/Workspace/Users/juann.perri@gmail.com/visagio/tarefa_2/landing"
table_ptax = f"{bronze_schema}.ptax_dolar"

_URL = ("https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
        "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)")


def table(schema: str, name: str) -> str:
    """Ex.: table(silver_schema, 'filmes') -> 'medalhao_cinema.silver.filmes'"""
    return f"{schema}.{name}"
def ingerir_ptax(spark, data_inicial, data_final):
    """data_inicial e data_final: objetos date/datetime. Busca na API e grava a tabela bronze."""
    top = 1000
    skip = 0
    dados = []

    with requests.Session() as session:
        while True:
            params = {
                "@dataInicial": f"'{data_inicial:%m-%d-%Y}'",
                "@dataFinalCotacao": f"'{data_final:%m-%d-%Y}'",
                "$format": "json",
                "$top": top,
                "$skip": skip,
            }
            resposta = session.get(_URL, params=params, timeout=60)
            resposta.raise_for_status()
            pagina = resposta.json()["value"]
            dados.extend(pagina)

            if len(pagina) < top:   # ultima pagina
                break
            skip += top

    if not dados:
        raise Exception("A API retornou lista vazia")

    # tuplas + schema explicito: nao depende de inferencia
    linhas = [(d["dataHoraCotacao"], float(d["cotacaoCompra"]), float(d["cotacaoVenda"]))
              for d in dados]
    df = (spark.createDataFrame(
              linhas, "data_hora_cotacao string, cotacao_compra double, cotacao_venda double")
          .withColumn("data_hora_cotacao", F.to_timestamp("data_hora_cotacao"))
          .withColumn("ingestao_ts", F.current_timestamp()))

    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {bronze_schema}")
    df.write.mode("overwrite").saveAsTable(table_ptax)
    return df