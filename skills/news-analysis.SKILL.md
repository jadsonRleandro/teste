---
name: news-analysis
description: 'Analyze and classify news articles for violence against women, with focus on identifying potential feminicide cases per Brazilian law'
tags: [content-analysis, classification, news, violence-detection]
---

# News Analysis and Classification Skill

## Purpose
Extracts critical information from news articles and classifies them against Brazil's feminicide law (Lei nº 13.104/2015) to identify cases involving violence against women.

## Workflow

### Step 1: Set Up Context
Provide the LLM with the legal framework and output requirements:
- Define feminicide classification criteria per Lei nº 13.104/2015 (homicide qualified when woman's death occurs in domestic/family violence context or due to gender discrimination)
- Specify that feminicide carries sentences of 12-30 years
- Establish that analysis must be objective and fact-based, excluding speculation

### Step 2: Extract Key Information
The LLM identifies and extracts:
- **Title**: Article headline
- **Resumo**: Concise summary with key facts only (location, people involved, cause, date)
- **Local**: State where incident occurred
- **Feminicídio**: Classification as "é uma noticia" (is a feminicide case) or "não é uma noticia" (is not)

### Step 3: Return Structured Output
Response must be valid JSON with no additional text:
```json
{
  "feminicidio": "é uma noticia ou não é uma noticia",
  "title": "Article title",
  "resumo": "Summary of the news",
  "local": "State only"
}
```
If any field cannot be determined, use: `"Não Encontrado"`

## System Prompt Template

Use this prompt with your LLM to initialize the news analysis workflow:

```
Você é um assistente de notícias, que tem a função de resumir as notícias com os pontos mais importantes, como o local do acontecimento, as pessoas envolvidas, o motivo do acontecimento e a data do acontecimento. Você deve responder apenas com o resumo da notícia, sem adicionar nenhuma informação extra ou opinião pessoal. Você deve ser objetivo e claro em suas respostas. Utilize o exemplo de resposta como saída.

Antes de tudo, faça uma verificação no texto e identifique com base na Lei do Feminicídio (Lei nº 13.104/2015): Reforça o combate à violência contra a mulher ao classificar o feminicídio como homicídio qualificado, uma modalidade de crime hediondo, quando a morte da mulher ocorre em contexto de violência doméstica e familiar, menosprezo ou discriminação de gênero. Esse crime abranda penas mais altas, de 12 a 30 anos na legislação brasileira.

A saída deve ser exatamente nesse formato, não deve ser adicionado nada além disso (caso algum dos campos não obtiver resposta coloque "Não Encontrado"):
{
  "feminicidio": "é uma noticia / não é uma noticia",
  "title": "titulo",
  "resumo": "resumo",
  "local": "Apenas Estado"
}
```

## Usage Examples

### Example Prompt
```
Analyze this news article and classify it according to the news analysis workflow:

[Insert article text here]
```

### Expected Output
```json
{
  "feminicidio": "é uma noticia",
  "title": "Mulher é morta por companheiro em São Paulo",
  "resumo": "Mulher foi encontrada morta após violência doméstica em contexto de discriminação de gênero no dia 15 de junho de 2026 em São Paulo, envolvendo agressão do parceiro.",
  "local": "São Paulo"
}
```

## Key Features

- **Legal Framework**: Grounded in Lei nº 13.104/2015 (Brazilian feminicide law)
- **Objective Analysis**: Excludes speculation and personal interpretation
- **Structured Output**: Valid JSON format for downstream processing
- **Fact-Based Classification**: Categorizes based on legal criteria, not assumptions
- **Fallback Handling**: Provides "Não Encontrado" for incomplete data

## Customization Points

- **Adjust Prompt Language**: Modify to target other languages or legal jurisdictions
- **Extend Fields**: Add additional extraction fields (e.g., victim age, weapon type, suspect relationship)
- **Threshold Tuning**: Refine classification criteria based on additional legal interpretations
- **Integration**: Pair with batch processing for analyzing multiple articles

## Related Skills & Customizations

- `content-filtering`: Filter articles by topic or sensitivity level
- `fact-verification`: Cross-reference extracted facts against databases
- `batch-processing`: Apply this skill to large news datasets
- `multilingual-analysis`: Adapt prompt for other languages

---

**Version**: 1.0  
**Last Updated**: 2026-06-18  
**Context**: VeritasIA backend LLM integration
