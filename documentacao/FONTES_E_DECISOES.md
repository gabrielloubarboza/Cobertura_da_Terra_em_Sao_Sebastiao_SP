# Fontes e decisões metodológicas — Etapa 1

## 1. Cena Sentinel-2 utilizada

| Item | Valor |
|---|---|
| Satélite / sensor | Sentinel-2A / MSI (MultiSpectral Instrument) |
| Produto (identificador ESA) | `S2A_MSIL2A_20260417T131301_N0512_R138_T23KMP_20260417T224715.SAFE` |
| Identificador no catálogo Copernicus Data Space (OData) | `b793e4a3-cc98-4e60-adce-5e5e09c4fcc1` |
| Identificador no espelho STAC (Earth Search) | `S2A_T23KMP_20260417T131303_L2A` (coleção `sentinel-2-c1-l2a`) |
| Data e hora da aquisição (UTC) | 17/04/2026, 13:13:01 (≈ 10:13 no horário de Brasília) |
| Nível de processamento | Level-2A — reflectância de superfície (BOA), baseline 05.12 |
| Órbita relativa / tile MGRS | R138 / 23KMP |
| Resolução espacial | B02, B03, B04, B08: 10 m · B11 e SCL: 20 m |
| Projeção original | WGS 84 / UTM zona 23S (EPSG:32723) |
| Nuvens (cena inteira, metadado ESA) | 0,34 % (`Cloud_Coverage_Assessment` = 0,341688) |
| Nuvens/sombras na área de estudo (SCL) | 0,053 % (48 pixels de 10 m, classes 8 e 9); sombra de nuvem: 0 %; área escura/sombra topográfica: 0,044 % |
| Elevação solar | 47,3° |
| Escala dos valores | reflectância = (DN − 1000) / 10000 (`BOA_ADD_OFFSET` = −1000; `BOA_QUANTIFICATION_VALUE` = 10000, conforme o MTD_MSIL2A) |

**Procedência e obtenção.**

- O produto foi localizado e conferido no catálogo do Copernicus Data Space Ecosystem
  (`https://catalogue.dataspace.copernicus.eu/odata/v1/Products?$filter=Name eq '<produto>'`),
  que confirma o nome, o identificador, a data e o caminho `/eodata/Sentinel-2/MSI/L2A/2026/04/17/...`.
- O download no Copernicus exige conta e baixa o produto completo (852 MB). Por isso, os pixels
  foram lidos do espelho público oficial em Cloud Optimized GeoTIFF mantido pela Element 84 no
  AWS Open Data (catálogo Earth Search, `https://earth-search.aws.element84.com/v1`). Nele se lê
  apenas a janela necessária, sem autenticação. O item do espelho tem o mesmo `s2:product_uri`
  do produto ESA, e os metadados originais (MTD_MSIL2A e MTD_TL) foram baixados com as bandas.
- Janela baixada: área de estudo + 1 km de margem (5 × 5 km), em EPSG:32723. Os valores DN não
  foram alterados. URLs, tamanhos e MD5 estão em `dados/fontes_manifesto.json`.
- Para visualizar a cena no navegador: Copernicus Browser (`https://browser.dataspace.copernicus.eu/`),
  Sentinel-2 L2A, data 17/04/2026, tile 23KMP.

**Licença e crédito.** Os dados Copernicus Sentinel são de acesso livre, completo e aberto
(Regulamento Delegado (UE) nº 1159/2013 e aviso legal dos dados Copernicus Sentinel). Crédito a
usar: *"Contém dados Copernicus Sentinel modificados [2026], processados no QGIS"*.

### Por que esta cena (triagem)

A porcentagem de nuvens informada para a cena (110 × 110 km) não representa Maresias. O script
`scripts/00_triagem_cenas.py` mediu a SCL numa janela de 8 × 8 km em torno da vila para as 32
cenas de abr/2025 a out/2026 com menos de 15 % de nuvens na cena. A lista completa está em
`documentacao/triagem_cenas.txt`. Exemplos:

| Data | Nuvem na cena | Nuvem/sombra local (8 × 8 km) | Sombra topográfica local |
|---|---|---|---|
| 26/03/2026 | 12,3 % | **78,7 %** | 0,0 % |
| 04/09/2026 | 4,7 % | **52,0 %** | 0,2 % |
| 28/12/2025 | 4,0 % | 0,00 % | 0,14 % |
| **17/04/2026** | **0,3 %** | **0,01 %** | **0,7 %** |
| 18/08/2026 | 3,8 % | 0,00 % | 0,7 % |
| 19/07/2026 | 0,0 % | 0,00 % | 1,9 % (sol mais baixo no inverno) |

A tabela mostra o problema: cenas com "poucas nuvens" no total podem ter a área coberta (26/03/2026).
Três cenas ficaram praticamente limpas e foram comparadas dentro da área de 3 × 3 km:

| Cena | Nuvem/sombra na área | Sombra topográfica | AOT médio (aerossóis) |
|---|---|---|---|
| 17/04/2026 | 0,053 % | 0,044 % | **0,071** |
| 28/12/2025 | 0,000 % | 0,013 % | 0,083 |
| 18/08/2026 | 0,004 % | 0,000 % | 0,077 |

A cena de 17/04/2026 foi mantida por três motivos: tem a atmosfera mais limpa (menor AOT), é mais
recente que a de dezembro e os 48 pixels marcados como nuvem são falsos positivos (ver § 4.3). As
outras duas cenas também seriam adequadas.

## 2. Área de estudo

- **Local:** Maresias, São Sebastião/SP. O recorte inclui a vila, a praia, a planície costeira e a
  encosta florestada da Serra do Mar.
- **Polígono:** `dados/area_estudo_maresias.gpkg`, 3 × 3 km = 9,000 km², EPSG:31983.
  - X de 440 940 a 443 940 m; Y de 7 368 140 a 7 371 140 m.
  - Em graus (SIRGAS 2000): de 45,5796° O / 23,7698° S a 45,5503° O / 23,7970° S; centro em 45,5650° O / 23,7834° S.
- **Por que este recorte:** a área reúne, em pouco espaço, contrastes visíveis na imagem: floresta
  contínua na encosta, mancha urbana densa, lotes abertos com gramíneas ou solo, faixa de praia e mar.
  O oceano ocupa 1,35 km² (15 %), e o restante (7,65 km²) é área não-água válida. A parte terrestre
  dentro do limite municipal do IBGE soma 7,76 km². A diferença para 7,65 km² vem da linha de costa
  do IBGE na escala 1:250 000 e dos pixels mistos da orla.
- **Ajuste à grade:** os limites são múltiplos de 20 m e coincidem com as bordas dos pixels do tile
  23KMP. Assim, o recorte não desloca nem reamostra as bandas de 10 m.
- Maresias não apresentou dificuldade que justificasse trocar de local.

## 3. Contexto oficial (IBGE)

| Camada | Fonte | Edição / arquivo |
|---|---|---|
| Bioma | IBGE — *Biomas e Sistema Costeiro-Marinho do Brasil*, 1:250 000 (página `15842-biomas.html?edicao=45164`) | Edição 2025, arquivo `lml_bioma_e250k_v20250911_A.shp` |
| Limite municipal | IBGE — Malha Municipal 2024 (SP) | `SP_Municipios_2024.shp`, CD_MUN 3550704 |

- A área de estudo está inteiramente no bioma **Mata Atlântica**. O teste automático confirma que só
  esse bioma intersecta o recorte.
- **Para a fotointerpretação:** a Mata Atlântica do litoral norte paulista é floresta ombrófila
  densa, com dossel fechado. Na imagem aparece como verde-escuro e textura rugosa na cor verdadeira,
  vermelho intenso na falsa-cor e NDVI ≈ 0,85–0,93.
- **Relevo, vegetação e ocupação:** a Serra do Mar chega quase até a praia. A ocupação se concentra
  na planície costeira estreita e avança pelos vales e pelo sopé da encosta, de modo que a borda entre
  urbano e floresta é recortada. As encostas íngremes concentram a floresta mais contínua.
- **Limitações:** o polígono do bioma (1:250 000) é contexto territorial e não identifica vegetação
  nativa na imagem. Um recorte de 9 km² não representa o município nem o bioma. O NDVI alto indica
  vegetação densa e fotossinteticamente ativa, mas não distingue mata nativa, secundária ou plantada.

## 4. Decisões de processamento

### 4.1 Sistema de referência
- Análises em **SIRGAS 2000 / UTM 23S (EPSG:31983)**.
- As bandas foram reprojetadas de EPSG:32723 para EPSG:31983 com o algoritmo GDAL "Reprojetar"
  (Warp). Na prática, WGS 84 e SIRGAS 2000 coincidem dentro da precisão do dado (a transformação
  padrão do PROJ entre os dois é nula). O teste automático confirmou que a B04 recortada é idêntica,
  pixel a pixel, à janela original.

### 4.2 Reamostragem e grade
- Grade comum: 300 × 300 pixels de 10 m, origem (440 940; 7 371 140).
- B02, B03, B04, B08: vizinho mais próximo. Como a grade de destino coincide com a original, não há
  reamostragem efetiva.
- **SCL (categórica): vizinho mais próximo.** Cada pixel de 20 m vira 2 × 2 pixels de 10 m com o mesmo
  código. Interpolar códigos de classe criaria valores sem significado.
- **B11 (contínua, 20 m → 10 m): bilinear.** A B11 não entra no NDVI. Foi preparada para a Etapa 2,
  e seu detalhe efetivo continua sendo de 20 m.

### 4.3 Nuvens, sombras e NoData
- A máscara vem da SCL (Scene Classification Layer) do próprio produto L2A.
- **Inválidas:** 0 sem dado, 1 saturado/defeituoso, 3 sombra de nuvem, 8 e 9 nuvem, 10 cirro, 11 neve.
- **Mantida:** classe 2 (área escura / sombra topográfica, 0,044 % da área). É terreno real em
  encosta sombreada. Excluí-la retiraria floresta de forma sistemática.
- Resultado: 48 pixels inválidos em 90 000 (0,053 %). Na inspeção visual da composição de cor
  verdadeira, esses pixels ficam sobre a areia clara e a arrebentação da praia central e não há nuvem
  visível no local. Têm reflectância alta em todas as bandas visíveis (B02 ≈ 0,19; B04 ≈ 0,28), típica
  de areia seca. São, portanto, provável falso positivo da SCL. Foram mantidos mascarados por
  precaução, com efeito desprezível (0,48 ha).
- NoData: 0 nos rasters em DN (padrão L2A) e −9999 nos rasters de reflectância e NDVI.

### 4.4 Reflectância
- reflectância = (DN − 1000) / 10000. O deslocamento de −1000 vale para produtos com baseline ≥ 04.00
  (desde 25/01/2022) e está declarado no MTD_MSIL2A. Sem ele, a reflectância fica 0,1 acima do correto
  e o NDVI fica distorcido.
- Erro encontrado e corrigido: na primeira execução, `A − 1000` foi calculado em inteiro sem sinal
  (UInt16). Os DN abaixo de 1000 "deram a volta" (995 − 1000 → 65 531), e a B08 chegou a 6,55. A
  fórmula passou a converter para número real antes da subtração. Depois da correção, a B08 varia de
  −0,0005 a 0,876.
- Os valores negativos muito pequenos (sobre a água) são efeito da correção atmosférica e do
  deslocamento. Foram mantidos na reflectância.

### 4.5 NDVI
- NDVI = (B08 − B04) / (B08 + B04), calculado sobre as reflectâncias alinhadas.
- Proteções: NoData herdado da máscara, e NDVI só onde B04 > 0 e B08 > 0, o que exclui 3 pixels de
  água com B08 levemente negativa. Com reflectância negativa no denominador, o índice sairia do
  intervalo [−1, 1]. Com essas condições, a soma B08 + B04 nunca é zero.

### 4.6 Contraste das composições
- O contraste é só de visualização: os limites mínimo e máximo do renderizador são os percentis 2 % e
  98 % de cada banda. Os arquivos de reflectância não foram alterados.

## 5. Viabilidade das classes para a Etapa 2 (avaliação preliminar)

> **Atualização da Etapa 2:** as §§ 5 e 6 registram a avaliação preliminar feita na Etapa 1. O
> método realmente aplicado está em [METODO_CLASSIFICACAO.md](METODO_CLASSIFICACAO.md).
>
> Duas avaliações abaixo foram revistas com dados:
> - **Areia de praia.** A faixa seca tem 3 a 8 pixels de largura, não 1 a 3, e é separável pelo
>   brilho (B02 ≈ 0,25) combinado com a conexão com a água. Virou a classe 5.
> - **Solo exposto dos lotes.** Continua inseparável do construído e foi incluído na classe 3.

Valores médios de amostras escolhidas por interpretação visual (janelas de 10 × 10 a 40 × 40 pixels).
Servem só para avaliar a separabilidade. **Não são amostras de treinamento nem validação.**

| Feição amostrada | B02 | B03 | B04 | B08 | B11 | NDVI | NDWI* |
|---|---|---|---|---|---|---|---|
| Floresta (encosta) | 0,021 | 0,039 | 0,020 | 0,321 | 0,139 | 0,88 | −0,78 |
| Urbano denso | 0,068 | 0,092 | 0,107 | 0,231 | 0,265 | 0,38 | −0,43 |
| Urbano (eixo norte) | 0,073 | 0,092 | 0,105 | 0,198 | 0,274 | 0,31 | −0,37 |
| Lote aberto com gramíneas (oeste) | 0,036 | 0,065 | 0,063 | 0,286 | 0,253 | 0,64 | −0,63 |
| Lote aberto com solo/gramíneas (centro) | 0,060 | 0,088 | 0,102 | 0,262 | 0,294 | 0,45 | −0,50 |
| Oceano | 0,035 | 0,036 | 0,009 | 0,003 | 0,003 | −0,50 | 0,85 |
| Arrebentação (espuma) | 0,147 | 0,168 | 0,116 | 0,060 | 0,028 | −0,41 | 0,47 |

\*NDWI = (B03 − B08) / (B03 + B08), índice de água de McFeeters. Será calculado na Etapa 2.

NDVI mediano por classe da SCL: vegetação 0,898; não vegetado 0,245; água −0,529.

| Classe candidata | Avaliação |
|---|---|
| 1. Vegetação arbórea | **Viável.** NDVI ≈ 0,85–0,93 e B11 baixa (≈ 0,14–0,17). Ainda assim, não pode ser chamada de "nativa" só pelo NDVI. |
| 2. Vegetação baixa ou aberta | **Viável, com ressalvas.** NDVI intermediário (≈ 0,45–0,70) e B11 mais alta (≈ 0,25–0,29). Pode ser confundida com bordas de floresta, quintais arborizados e pixels mistos no urbano. |
| 3. Superfícies urbanizadas | **Viável como "área urbanizada mista".** Em 10 m, telhados, ruas e quintais se misturam, e o NDVI fica entre ≈ 0,3 e 0,4. Não é uma classe de superfície 100 % impermeável. |
| 4. Água | **Viável.** NDVI < 0 e NDWI > 0,4 no oceano e na arrebentação. Não há corpo d'água continental com largura suficiente para 10 m. |
| 5. Solo exposto | **Não separável com segurança.** A areia da praia é brilhante, mas forma uma faixa de 1–3 pixels misturada com água e urbano, e parte dela foi mascarada. O solo dos lotes aparece misturado com gramíneas e com resposta próxima à do urbano. |

## 6. Método recomendado para a Etapa 2

Classificação **exploratória por regras** (árvore de decisão simples), feita na Calculadora Raster do
QGIS sobre a pilha de reflectância, e complementada por conferência visual:

1. Calcular o NDWI = (B03 − B08) / (B03 + B08).
2. Aplicar as regras em ordem, com limiares definidos pelos histogramas e conferidos visualmente
   (os valores abaixo são apenas indicativos):
   - máscara = 0 → **sem dado**;
   - NDWI > ≈ 0,2 → **água**;
   - NDVI ≥ ≈ 0,75 e B11 ≤ ≈ 0,20 → **vegetação arbórea**;
   - NDVI ≥ ≈ 0,45 (demais casos) → **vegetação baixa ou aberta**;
   - restante → **superfícies urbanizadas / não vegetadas**.
3. Consolidar "solo exposto" com "urbanizado / não vegetado". Se for desejável mostrar a praia, a
   alternativa é uma revisão manual pontual (digitalização da faixa de areia) e não uma regra
   espectral.
4. Opcional: eliminar fragmentos de 1–2 pixels com `gdal:sieve` (Raster > Análise > Peneira).
5. Conferência: cerca de 50–100 pontos aleatórios (Vetor > Ferramentas de pesquisa > Pontos
   aleatórios dentro de polígonos), rotulados visualmente na cor verdadeira e na falsa-cor, com uma
   matriz de confusão simples. A limitação deve ser declarada: a referência é a própria imagem, sem
   dados de campo.
6. Calcular as áreas por classe sobre a **área terrestre válida** (excluindo água e pixels mascarados)
   como denominador.

Não se recomenda classificação supervisionada nem aprendizado de máquina para este exercício.
