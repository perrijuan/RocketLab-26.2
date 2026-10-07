# Medalhão Cinema

Projeto desenvolvido no Databricks utilizando **PySpark** e **Delta Lake** para processamento e armazenamento dos dados.
O pipeline foi construído em camadas **Landing, Bronze, Silver e Gold**, seguindo uma arquitetura de Data Lakehouse.
Na camada Bronze, os dados foram ingeridos e armazenados preservando o histórico das cargas.
Na Silver, foram realizados tratamentos, padronização, deduplicação e validações de qualidade dos dados.
A cotação do dólar foi obtida através da API **PTAX do Banco Central** utilizando a biblioteca `requests`.
Na Gold, foi construída uma modelagem dimensional (**Star Schema**) com fatos, dimensões e tabelas ponte.
As transformações e manipulações dos dados foram realizadas principalmente com as funções do **PySpark**.
As tabelas foram armazenadas em formato **Delta**, permitindo maior controle e confiabilidade no ambiente Databricks.
