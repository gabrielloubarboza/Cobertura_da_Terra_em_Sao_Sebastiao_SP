# Método da classificação exploratória — Etapa 2

Imagem: Sentinel-2A MSI L2A de 17/04/2026
(`S2A_MSIL2A_20260417T131301_N0512_R138_T23KMP_20260417T224715.SAFE`). Recorte: Maresias,
3 × 3 km, EPSG:31983, pixel de 10 m.

A classificação é **exploratória e baseada em regras explícitas**:

- não é supervisionada (nenhum classificador foi treinado);
- não usa aprendizado de máquina;
- não reaproveita mapa pronto, como o MapBiomas.

O resultado descreve **cobertura observável** na data da imagem. Não descreve uso da terra nem
origem da vegetação.

## 1. Índices usados

| Índice | Fórmula | Para que foi usado | Observação |
|---|---|---|---|
| NDVI | (B08 − B04) / (B08 + B04) | separar vegetação de não vegetação; floresta de vegetação aberta | Reutilizado da Etapa 1 |
| NDWI (McFeeters) | (B03 − B08) / (B03 + B08) | água superficial | Índice de água com verde e NIR. Não é o "NDWI de vegetação" de Gao, feito com NIR e SWIR |
| NDBI | (B11 − B08) / (B11 + B08) | desempate entre floresta e vegetação aberta quando o NDVI fica entre 0,75 e 0,80 | A B11 tem 20 m nativos, reamostrados para 10 m por bilinear na Etapa 1. O detalhe efetivo é de 20 m. Para separar áreas construídas, o NDBI **não** foi útil (ver § 3) |
| B02 (reflectância) | banda azul | identificar superfícies muito claras (areia) | Usada direto, sem criar novo índice |

Proteções:

- NoData herdado da máscara;
- divisão só onde o denominador é maior que 0;
- no NDWI e no NDBI, reflectâncias levemente negativas (3 pixels de água com B08 = −0,0005)
  são tratadas como 0, para manter o índice em [−1, 1].

Arquivos: `processamento/NDWI_20260417.tif` e `processamento/NDBI_20260417.tif`.

## 2. Amostras exploratórias e limiares

Foram desenhadas 17 amostras retangulares (de 24 a 4 250 pixels), alinhadas à grade, por
interpretação da cor verdadeira e da falsa-cor. Elas estão em `amostras_calibracao` no
GeoPackage e as estatísticas completas em `documentacao/estatisticas_amostras.csv`.
**Elas serviram só para definir limiares e foram excluídas do sorteio dos pontos de conferência.**

| Grupo de amostras | NDVI (média ± dp) | NDWI (faixa) | NDBI (média) | B02 |
|---|---|---|---|---|
| Floresta (ARB1–ARB5) | 0,83–0,90 ± 0,01–0,17 | −0,88 a −0,21 | −0,34 a −0,40 | 0,014–0,036 |
| Vegetação aberta (ABE1–ABE3) | 0,64–0,65 ± 0,06–0,12 | −0,82 a −0,51 | −0,07 a −0,08 | 0,033–0,035 |
| Construído / solo (URB1–URB4, SOL1) | 0,31–0,45 ± 0,10–0,21 | −0,85 a +0,07 | −0,02 a +0,17 | 0,06–0,08 |
| Areia de praia (ARE1, ARE2) | 0,04–0,07 | −0,35 a −0,07 | +0,05 a +0,11 | **0,25–0,26** |
| Água (AGU1 oceano, AGU2 arrebentação) | −0,50 | **+0,31 a +0,92** | −0,03 a +0,09 | 0,04–0,11 |

Os histogramas da área inteira estão em `documentacao/figuras/06_histogramas_indices.png`.

| Limiar | Valor | Justificativa |
|---|---|---|
| Água | NDWI > **0,20** | Vale do histograma: a terra vai até ≈ 0,07 e a água começa em ≈ 0,31. 0,20 fica no ponto médio |
| Arbórea | NDVI ≥ **0,80**, ou NDVI ≥ **0,75** com NDBI ≤ **−0,20** | Floresta pura ≥ 0,78. Na faixa 0,75–0,80 o NDBI separa floresta (≈ −0,4) de gramado denso (≈ −0,07) |
| Vegetação intermediária | NDVI ≥ **0,55** | Ponto de igual densidade entre construído (0,38 ± 0,19) e vegetação aberta (0,645 ± 0,09) |
| Superfície clara | B02 ≥ **0,15** e NDVI < 0,20 | Areia ≈ 0,25 contra construído ≤ 0,08 |

## 3. Regras, na ordem de aplicação

| Ordem | Regra | Resultado |
|---|---|---|
| R0 | máscara SCL = 0 | **9** pixel inválido (sem classe temática) |
| R1 | NDWI > 0,20 | **4** água |
| R2 | NDVI ≥ 0,80, ou (NDVI ≥ 0,75 e NDBI ≤ −0,20) | **1** vegetação arbórea |
| R3 | NDVI ≥ 0,55 | candidato a vegetação aberta |
| R4 | B02 ≥ 0,15 e NDVI < 0,20 | candidato a areia |
| R5 | restante | **3** superfícies construídas e outras não vegetadas |

Regras de contexto (interpretação visual traduzida em regra reproduzível):

- **C1 — areia:** o candidato a areia só vira **5** se a mancha clara toca a água. Manchas claras
  isoladas, como telhados claros, voltam para 3. Ferramentas: Poligonizar, Extrair por
  localização e Rasterizar.
- **C2 — vegetação aberta:** o candidato só vira **2** se, depois de remover as partes com até
  20 m de largura (buffer −10 m e depois +10 m), sobra uma mancha de pelo menos 0,1 ha. O resto
  vira **6** (transição/mistura): franjas de borda e fragmentos de quintal.
- **C3 — dossel:** um fragmento 6 de até 4 pixels, cercado só por arbórea, vira **1**. Ele é
  variação de iluminação do dossel contínuo, não uma transição. Afetou 103 pixels na versão
  final; antes da correção de R2 (§ 5) eram 699.

Por que essas regras de contexto? Na resolução de 10 m, a resposta espectral intermediária
(NDVI 0,55–0,75) é igual em um gramado e em um pixel que mistura telhado e copa. A forma e o
tamanho da mancha são a evidência adicional disponível. Nenhum limite foi desenhado à mão.

**NDBI e áreas construídas.** O construído (NDBI −0,02 a +0,17) se sobrepõe ao solo exposto
(+0,07), à areia (+0,05 a +0,11) e até à água (+0,09). Por isso o NDBI **não** foi usado para
definir área construída.

## 4. Revisão visual e correções

A classificação foi comparada com a cor verdadeira, a falsa-cor, o NDVI e o NDBI em ampliações
de quatro setores: oeste, leste, norte e orla.

| Achado | Decisão |
|---|---|
| Pixels isolados de "transição" dentro da floresta contínua | Corrigido pela regra C3 |
| Telhados claros longe da praia caindo como areia | Corrigido pela regra C1 (conexão com a água) |
| Faixa de areia úmida (B02 entre 0,12 e 0,15) mapeada como 3 | **Não corrigido.** Baixar o limiar para 0,12 levava areia para dentro de quadras da orla leste. Fica como confusão conhecida |
| 2 pixels de "água" no continente (borda oeste) | Mantidos. São turquesa na cor verdadeira, provável piscina, ou seja, água artificial |
| 48 pixels mascarados sobre a areia | Mantidos como 9 (inválido), sem classe atribuída. Têm perfil espectral de areia, mas a exclusão da Etapa 1 foi preservada |
| **Bordas de floresta mapeadas como vegetação aberta** (achado da rodada diagnóstica) | **Corrigido na regra R2.** Ver § 5 |

## 5. Conferência exploratória

### Rodada 1 — diagnóstica (semente 2026)

- 80 pontos estratificados, numa versão anterior da classificação em que a regra R2 exigia
  sempre NDBI ≤ −0,20.
- Concordância bruta: 54/80.
- A classe 2 concordou em só 2 de 10 pontos, e 5 deles eram borda de floresta.
- **Causa:** a B11 de 20 m "contamina" o NDBI nas bordas. NDBI > −0,20 ocorre em 12 % dos pixels
  de borda florestal e em 1 % do interior.
- **Correção:** NDVI ≥ 0,80 dispensa o NDBI.
- A correção foi avaliada **apenas nas amostras de calibração**: ARB3 subiu de 95 % para 100 % e
  ARB4 de 86 % para 98 %, sem alterar as amostras de vegetação aberta.
- Como a rodada 1 orientou a correção, ela **deixou de ser conferência independente** e ficou
  como registro em `documentacao/diagnostico_1/`.

### Rodada 2 — conferência final (semente 2027)

> Conferência interna exploratória de 80 pontos, realizada por interpretação assistida por IA (Claude) sobre a própria cena Sentinel-2, sem referência independente ou validação de campo.

- **Desenho:** aleatório estratificado pela classe mapeada, com semente fixa 2027. Os estratos são
  ordenados por classe antes do sorteio.
- **Alocação:** 20 arbórea, 10 aberta, 18 construída, 8 água, 8 areia e 16 transição. Total de 80.
- **Restrições:** distância mínima de 20 m na mesma classe. Ficaram de fora as amostras de
  calibração, um raio de 15 m em torno dos pontos da rodada 1 e os pixels inválidos.
- **Repetibilidade:** o script 08 foi executado duas vezes, em processos separados, e gerou os
  mesmos 80 pontos. O teste 18 repete essa verificação.
- **Interpretação:** às cegas, sem ver a classe mapeada, por fichas com cor verdadeira e falsa-cor
  numa janela de 150 m (`documentacao/diagnostico_2/fichas_pontos_NN.png`).
  - **Quem interpretou:** Claude (assistente de IA), sobre a própria imagem Sentinel-2.
  - **Critério:** a cobertura dominante do pixel. Quando nenhuma domina, o ponto é registrado
    como 6 (mistura).
  - **Revisão:** o usuário deve rever os pontos no QGIS (camada "Pontos de conferência").
- **Fonte de referência:** apenas a própria imagem. Não foram usadas imagens de alta resolução,
  porque as gratuitas disponíveis têm data desconhecida ou diferente e restrições de uso.

| mapeada \ interpretada | 1 | 2 | 3 | 4 | 5 | 6 | total | concordantes |
|---|---|---|---|---|---|---|---|---|
| 1 Vegetação arbórea | **20** | 0 | 0 | 0 | 0 | 0 | 20 | 20 |
| 2 Vegetação baixa ou aberta | 3 | **3** | 0 | 0 | 0 | 4 | 10 | 3 |
| 3 Construídas / não vegetadas | 2 | 1 | **10** | 1 | 0 | 4 | 18 | 10 |
| 4 Água | 0 | 0 | 0 | **8** | 0 | 0 | 8 | 8 |
| 5 Areia de praia | 0 | 0 | 0 | 2 | **6** | 0 | 8 | 6 |
| 6 Transição / mistura | 4 | 1 | 2 | 0 | 0 | **9** | 16 | 9 |
| total | 29 | 5 | 12 | 11 | 6 | 17 | 80 | **56** |

**Leitura correta da tabela:**

- 56/80 pontos (70,0 %) tiveram a mesma classe no mapa e na interpretação visual. Isso é uma
  **conferência interna**: a referência é a mesma imagem, interpretada pelo mesmo processo que
  desenhou as amostras.
- **Não** é uma estimativa de acurácia temática.
- **Não** é ponderada por área, porque a amostra é estratificada e as classes pequenas foram
  superamostradas.
- **Não** substitui validação de campo nem imagens independentes.

**Principais confusões:**

- **Vegetação aberta × arbórea e transição.** Só 3 dos 10 pontos da classe 2 parecem vegetação
  aberta; os demais parecem borda arbórea (3) ou mistura (4). A classe 2 é a de **menor
  confiança**. Só o lote oeste (≈ 0,03 km²) e uma clareira junto à estrada são claramente
  vegetação aberta.
- **Construído × transição/arbórea.** Quadras com quintais arborizados: o mapa diz "construído", e
  a interpretação vê "mistura" (4) ou árvore (2).
- **Transição × arbórea.** Bordas de floresta com copas dominantes (4).
- **Areia/construído × água na zona de espraiamento.** Três pontos na faixa de areia molhada e
  espuma, mapeados como areia (2) ou como classe 3 (1), foram vistos como água rasa. O limite
  terra-mar varia com ondas e maré; nessa faixa de 1–2 pixels, nenhuma das duas leituras é segura.

### Prévia da rodada 2 (registro, não reprodutível)

- Antes da ordenação dos estratos, o mesmo script sorteou outros 80 pontos, porque a ordem das
  feições após "Dissolver" variava entre execuções.
- Esses pontos foram interpretados às cegas, com o mesmo critério, e deram **63/80** concordantes.
  Nenhuma regra foi alterada depois dessa prévia.
- O conjunto não pode ser sorteado de novo pelo script, por isso ficou só como registro, guardado
  fora deste repositório.
- As fichas da prévia foram sobrescritas por engano numa reexecução e não estão guardadas.
- A diferença entre 63/80 e 56/80 mostra como uma conferência de 80 pontos varia de uma amostra
  para outra. Mais um motivo para não tratar esses números como acurácia.

## 6. Limite terra-mar

- A linha de costa espectral (borda da classe Água) foi comparada com duas referências
  independentes:
  - **OpenStreetMap** (`natural=coastline`, traçada sobre imagens Bing em 2019–2020): distância
    mediana de **4,9 m**, P90 de 14 m;
  - **IBGE**, Malha Municipal 2024, escala 1:250 000: mediana de 38 m.
- Área não aquática:
  - espectral: 7,658 km²;
  - pela costa OSM: 7,655 km²;
  - pelo IBGE: 7,761 km².
- As proporções usam a **área não aquática identificada espectralmente** (7,66 km²), que concorda
  com a costa OSM em 0,003 km².
- Não é uma delimitação oficial da superfície terrestre.
- Detalhes em `documentacao/conferencia_linha_costa.txt`.

## 7. Escala de interpretação

Com pixel de 10 m (e 20 m no NDBI), o resultado serve para leitura de padrões em escala
aproximada de 1:25 000 ou menor. Não serve para limites de lote, de edificação ou de árvore
individual.

## 8. Cores do mapa (Etapa 3)

A paleta da Etapa 2 foi trocada na Etapa 3, sem alterar códigos nem valores:

- **Problema:** numa simulação de daltonismo (matrizes de Machado, 2009; distância em OKLab), a
  vegetação arbórea e as superfícies construídas ficavam quase iguais para protanopia (ΔE 2,1), e a
  arbórea e a água, para tritanopia (ΔE 2,7).
- **Paleta nova:**

  | Classe | Cor |
  |---|---|
  | 1 Arbórea | verde-escuro `#1e5a2c` |
  | 2 Aberta | verde-claro `#9ccc65` |
  | 3 Construída / não vegetada | cinza-violeta `#7e7a85`, neutro, sem sugerir "urbano" |
  | 4 Água | azul `#4a90d9` |
  | 5 Areia | bege `#f6e8b1` |
  | 6 Transição | laranja-avermelhado `#e86f3a` |
  | 9 Inválido | preto |

- **Resultado:** a menor distância entre classes passou a 10,4 nos quatro modos simulados (normal,
  protan, deutan, tritan).

