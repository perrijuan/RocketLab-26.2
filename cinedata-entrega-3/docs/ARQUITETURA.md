# Arquitetura, contratos e regras de negócio

## Fontes e Bronze

| Arquivo real do ZIP | Tabela Bronze |
|---|---|
| movies_info_TMDB_IMDB.csv | tb_movies_info |
| movies_financials_IMDB_TMDB.csv | tb_movies_financials |
| movies_metrics_IMDB_TMDB.csv | tb_movies_metrics |
| credits_and_tags_IMDB_TMDB.csv | tb_credits_and_tags |
| movies_reviews.csv | tb_movies_reviews |
| API PTAX | tb_cotacao_dolar |

O enunciado escreve `movies_info_IMDB_TMDB.csv`; o arquivo recebido usa `movies_info_TMDB_IMDB.csv`. A configuração aponta para o nome recebido. A Bronze adiciona `ingestion_datetime` e grava em Delta append. O código ainda usa `inferSchema=True`; isso precisa ser revisto para preservar representações originais como IDs com zeros à esquerda.

O módulo `medalhao_config.py` centraliza catálogo, schemas, caminho e função PTAX. A função usa paginação, timeout de 60 segundos e falha se a resposta não tiver dados. Também escreve `bronze.ptax_dolar` em overwrite antes do append do notebook em `tb_cotacao_dolar`; essa persistência adicional não é a tabela obrigatória e merece separação de responsabilidades.

## Silver: sete tabelas

| Tabela | Grão pretendido | Tratamento localizado |
|---|---|---|
| tb_info_filmes | Um filme | Renomeação, tradução de status, datas, ano e deduplicação por ingestão |
| tb_financeiro_filmes | Um filme | Decimal, ausências, USD/BRL, lucro e margem |
| tb_metricas_engajamento | Um filme | Popularidade, notas 0–10, votos e conversão segura |
| tb_avaliacoes_usuarios | Uma avaliação por filme/usuário/nota/comentário | Duplicatas, notas e comentário vazio |
| tb_generos | Um par filme/gênero | Split, explode, padronização e deduplicação |
| tb_pessoas_empresas | Filme/entidade/tipo | Ator, Diretor, Roteirista e Produtora |
| tb_cotacao_dolar | Um dia | Última observação diária e forward fill |

A escrita Silver usa Delta overwrite. A deduplicação por ingestão ainda não tem desempate para timestamps iguais. Algumas saídas mantêm `ingestion_datetime`, apesar do requisito de nomes em português.

### Dinheiro e câmbio

O parser financeiro reconhece inteiros, decimais com ponto/vírgula, milhares brasileiros/americanos e sufixo `M`. Ausências, zero e valores negativos em orçamento/receita tornam-se `NULL`. Prejuízo é permitido: lucro negativo não é invalidado. O financeiro usa `DECIMAL(18,2)`; BRL = USD × cotação de compra mais recente até a execução. Lucro = receita − orçamento; margem = lucro / receita × 100. Sem orçamento ou receita, o lucro permanece nulo.

A Silver preenche dias sem cotação com o último valor disponível. O calendário começa na primeira observação existente e vai até o maior valor entre a última observação e a data atual. Não há parâmetro de data de referência fixado. O resultado em BRL é uma conversão pela taxa utilizada na execução, não uma conversão histórica individual por lançamento.

`imports.py` contém um experimento separado de interpolação linear em `testes.tb_cotacao_fallback`, com `uso=TESTE`. Não substitui o forward fill exigido e não é um fallback automático que mantém a ingestão quando a API falha.

### Métricas, gêneros e entidades

Notas fora de 0–10 e popularidades/votos negativos são anulados. Há correções pontuais de popularidade para os IDs 809905, 658829, 557809 e 418746, condicionadas a valores específicos; não são um tratamento geral de todo Column Shift. A conversão de votos via double para int ainda pode truncar frações.

Gêneros são filtrados por expressão regular e quantidade de palavras. Entidades têm limite de 60 caracteres e seis palavras. Essas heurísticas não comprovam pertencimento ao domínio e podem descartar nomes legítimos. As avaliações são deduplicadas depois da normalização; notas inválidas diferentes podem convergir para a mesma combinação com NULL.

## Gold: contrato oficial

| Objeto | Grão e chave |
|---|---|
| dim_movies | Um filme; sk_movie_id BIGINT e id_filme natural |
| dim_genres | Um gênero; sk_genre_id BIGINT |
| dim_people | Nome e papel; sk_person_id BIGINT |
| dim_companies | Uma produtora por nome; sk_company_id BIGINT |
| dim_reviews | Resumo de avaliações por filme; sk_review_id e sk_movie_id BIGINT |
| bridge_movie_genre | Par filme/gênero |
| bridge_movie_person | Par filme/pessoa |
| bridge_movie_company | Par filme/produtora |
| fact_movies_performance | Um filme lançado, com métricas financeiras e engajamento |

A fato filtra `Lançado`, data não nula e data até hoje, preservando filmes sem métricas por left join. As avaliações são agregadas antes de relacionar com filmes. As bridges evitam incorporar relações multivaloradas diretamente à fato. Mesmo com bridges, um join analítico entre várias relações pode multiplicar valores: um filme com 2 gêneros, 3 atores e 2 produtoras poderia aparecer 12 vezes. Somar a receita nesse resultado inflaria o total.

O notebook contém dois ciclos de construção. Primeiro, gênero recebe SHA-256 textual; depois, recebe row_number BIGINT e as bridges são regravadas. A segunda sequência e a checagem final buscam o contrato BIGINT, mas uma falha intermediária pode deixar objetos incompatíveis. Chaves com row_number também podem mudar se o conjunto ordenado mudar; reprocessar dimensões e relações de forma coordenada é necessário.

## Seis perguntas de negócio

| Questão | Implementação encontrada e interpretação |
|---|---|
| 1. Receita total em BRL | Soma na fato, sem joins com bridges; universo de lançados com data válida, receitas nulas ignoradas |
| 2. Top 5 popularidade | Fato + filmes, exclui NULL, ordena valor decrescente e SK crescente, limita a 5 |
| 3. Filmes por gênero | Bridge + gênero, countDistinct de filmes; inclui o universo da dimensão, não apenas a fato |
| 4. Top 10 receita | RANK pela receita USD; ordena empates pela SK fora da janela e limita a 10; mostra USD e BRL |
| 5. Ator com mais participações | Últimos 24 meses relativos ao último lançamento realizado; mostra todos os empatados no primeiro lugar |
| 6. Produtora com maior lucro | Últimos 60 meses, soma lucros associados e mostra todas as primeiras colocadas empatadas |

As janelas usam início exclusivo e fim inclusivo: `(data_max − meses, data_max]`. A data atual apenas exclui futuros; o teto da janela é a maior data válida da base. A questão 1 usa o universo da fato, embora o texto diga “todos os filmes da base”; essa interpretação precisa ser apresentada junto ao resultado.

Em coproduções, todo o lucro do filme é atribuído a cada produtora associada, pois a base não informa participação contratual. Isso não mede quanto cada empresa efetivamente recebeu. Não se deve somar os totais das produtoras como lucro global.
