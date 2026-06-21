"""
SCRIPT: Consultar Part Number pelo Gemini Flash e API do Mercado Livre - LISTAR 20 ANÚNCIOS
Rodar no Claude
Retorna para cada anúncio: título (mais caracteres), valor, dimensões, tamanho, largura, altura, comprimento, peso
"""

import os

import requests
from google import genai
from google.genai import types

# ============================================
# CONFIGURAÇÃO
# ============================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")  # Defina a variável de ambiente GEMINI_API_KEY
mercado_livre_site = "MLB"  # Mercado Livre Brasil
NUMERO_ANUNCIOS = 20  # Número de anúncios para listar

# ============================================
# BUSCA POR FOTO
# ============================================

def extrair_part_number_da_foto(foto_bytes, mime_type="image/jpeg", gemini_api_key=None):
    """
    Usa o Gemini Flash (visão) para identificar o part number, marca e modelo
    da peça a partir de uma foto.
    """
    client = genai.Client(api_key=gemini_api_key or GEMINI_API_KEY)

    prompt = """
    Você é um especialista em autopeças e motopeças. Observe a foto da peça
    e identifique:
    - O part number/código gravado na peça (se visível)
    - A marca e modelo do veículo a que a peça provavelmente pertence
    - O nome da peça

    Retorne APENAS uma query de busca curta em português, otimizada para o
    Mercado Livre, combinando essas informações (ex: "capa lateral direita
    pulsar ns200 52jl2019"). Nada mais além da query.
    """

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Part.from_bytes(data=foto_bytes, mime_type=mime_type),
            prompt,
        ],
    )

    return response.text.strip()


# ============================================
# ESTIMATIVA DE DIMENSÕES (FALLBACK)
# ============================================

def estimar_dimensoes_gemini(titulo, gemini_api_key=None):
    """
    Quando o anúncio do Mercado Livre não informa dimensões/peso, pede ao
    Gemini Flash uma estimativa realista com base no título do produto.
    """
    client = genai.Client(api_key=gemini_api_key or GEMINI_API_KEY)

    prompt = f"""
    Estime as dimensões de envio (embalagem) e o peso para o seguinte produto
    de autopeça/motopeça, com base em padrões de mercado:

    Título: {titulo}

    Responda APENAS no formato exato abaixo, com números em cm e kg:
    altura=X.X|largura=X.X|comprimento=X.X|peso=X.XX
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        texto = response.text.strip()
        partes = dict(item.split("=") for item in texto.split("|"))
        return {
            "altura": partes.get("altura"),
            "largura": partes.get("largura"),
            "comprimento": partes.get("comprimento"),
            "peso": partes.get("peso"),
            "estimado": True,
        }
    except Exception:
        return {
            "altura": None,
            "largura": None,
            "comprimento": None,
            "peso": None,
            "estimado": True,
        }


# ============================================
# FUNÇÃO PRINCIPAL
# ============================================

def consultar_part_number_20_anuncios(part_number=None, gemini_api_key=None, foto_bytes=None, foto_mime_type="image/jpeg"):
    """
    Consulta um part number (texto ou identificado por foto) e lista 20
    anúncios do Mercado Livre.
    """

    # 0. Se uma foto foi enviada, usa o Gemini Vision para identificar a peça
    if foto_bytes:
        part_number = extrair_part_number_da_foto(
            foto_bytes, mime_type=foto_mime_type, gemini_api_key=gemini_api_key
        )

    if not part_number:
        return {"error": "Informe um part number, título da peça ou uma foto"}

    # 1. Configurar cliente Gemini Flash
    client = genai.Client(api_key=gemini_api_key or GEMINI_API_KEY)

    # 2. Usar Gemini Flash para gerar query de busca otimizada
    query_prompt = f"""
    Você está ajudando a buscar um produto no Mercado Livre Brasil.
    Part number ou descrição: {part_number}

    Gere uma query de busca otimizada em português para o Mercado Livre,
    incluindo marca e modelo da peça/veículo quando identificáveis.
    Inclua variações comuns do part number e termos relacionados.

    Retorne APENAS a query de busca em português, nada mais.
    """

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=query_prompt
    )

    query_otimizada = response.text.strip()

    # 3. Buscar no Mercado Livre usando a API pública
    search_url = f"https://api.mercadolibre.com/sites/{mercado_livre_site}/search?q={part_number}&limit={NUMERO_ANUNCIOS}"

    response_search = requests.get(search_url)

    if response_search.status_code != 200:
        return {"error": f"Erro na busca: {response_search.status_code}"}

    dados_busca = response_search.json()
    produtos = dados_busca.get('results', [])

    # 4. Alternar para query otimizada se não encontrar 20 produtos
    if len(produtos) < NUMERO_ANUNCIOS:
        search_url_otimizada = f"https://api.mercadolibre.com/sites/{mercado_livre_site}/search?q={query_otimizada}&limit={NUMERO_ANUNCIOS}"
        response_otimizada = requests.get(search_url_otimizada)

        if response_otimizada.status_code == 200:
            produtos_otimizados = response_otimizada.json().get('results', [])

            # Combinar resultados se ainda não atingimos 20
            if len(produtos) + len(produtos_otimizados) >= NUMERO_ANUNCIOS:
                produtos = produtos + produtos_otimizados
                produtos = produtos[:NUMERO_ANUNCIOS]  # Limitar a 20

    if not produtos:
        return {
            "error": "Nenhum produto encontrado para o part number",
            "part_number": part_number,
            "query_otimizada_gemini": query_otimizada
        }

    # 5. Processar cada produto e extrair todas as informações
    resultados = []
    anuncios_processados = 0

    print(f"\nProcessando {len(produtos)} produtos encontrados...")

    for produto in produtos:
        if anuncios_processados >= NUMERO_ANUNCIOS:
            break

        item_id = produto.get('id')

        # Buscar detalhes completos do item
        item_url = f"https://api.mercadolibre.com/items/{item_id}"
        response_item = requests.get(item_url)

        if response_item.status_code != 200:
            continue

        item_detalhes = response_item.json()

        # Extrair todas as informações solicitadas
        titulo = item_detalhes.get('title', '')
        valor = item_detalhes.get('price', 0)
        currency = item_detalhes.get('currency_id', 'BRL')

        # Dimensões e atributos
        dimensoes = None
        tamanho = None
        largura = None
        altura = None
        comprimento = None
        peso = None

        # Extrair de attributes
        attributes = item_detalhes.get('attributes', [])

        for attr in attributes:
            attr_name = attr.get('name', '')
            attr_value = attr.get('value_name', '')
            attr_value_string = attr.get('value_string', '')

            valor_final = attr_value if attr_value else attr_value_string

            if attr_name == 'DIMENSIONS' or 'dimens' in attr_name.lower():
                dimensoes = valor_final
            elif attr_name == 'SIZE' or 'tamanho' in attr_name.lower():
                tamanho = valor_final
            elif attr_name == 'WIDTH' or 'largura' in attr_name.lower():
                largura = valor_final
            elif attr_name == 'HEIGHT' or 'altura' in attr_name.lower():
                altura = valor_final
            elif attr_name == 'LENGTH' or 'comprimento' in attr_name.lower():
                comprimento = valor_final
            elif attr_name == 'WEIGHT' or 'peso' in attr_name.lower():
                peso = valor_final

        dimensoes_estimadas = False
        if not any([largura, altura, comprimento, peso]):
            estimativa = estimar_dimensoes_gemini(titulo, gemini_api_key=gemini_api_key)
            altura = estimativa["altura"]
            largura = estimativa["largura"]
            comprimento = estimativa["comprimento"]
            peso = estimativa["peso"]
            dimensoes_estimadas = True

        resultado = {
            "anuncio_numero": anuncios_processados + 1,
            "titulo": titulo,
            "numero_caracteres_titulo": len(titulo),
            "valor": valor,
            "currency": currency,
            "dimensoes": dimensoes,
            "tamanho": tamanho,
            "largura": largura,
            "altura": altura,
            "comprimento": comprimento,
            "peso": peso,
            "dimensoes_estimadas": dimensoes_estimadas,
            "item_id": item_id,
            "url": f"https://www.mercadolivre.com.br/{item_id}",
            "thumbnail": produto.get('thumbnail', ''),
            "condition": produto.get('condition', ''),
            "shiping": produto.get('shipping', {}).get('mode', 'N/A'),
            "location": produto.get('address', {}).get('city_id', 'N/A'),
            "part_number_encontrado": part_number
        }

        resultados.append(resultado)
        anuncios_processados += 1

    # 6. Encontrar o produto com título de mais caracteres
    if resultados:
        produto_mais_caracteres = max(resultados, key=lambda x: x['numero_caracteres_titulo'])

        return {
            "part_number": part_number,
            "query_otimizada_gemini": query_otimizada,
            "total_produtos_encontrados": len(produtos),
            "anuncios_listados": anuncios_processados,
            "produto_com_titulo_mais_caracteres": produto_mais_caracteres,
            "lista_20_anuncios": resultados
        }

    return {"error": "Nenhum produto válido encontrado"}


# ============================================
# EXEMPLO DE USO - LISTAR 20 ANÚNCIOS
# ============================================

if __name__ == "__main__":
    # Part number para consultar (exemplo)
    part_number = "OEM-123456"  # Substitua pelo part number desejado

    print(f"\n" + "="*80)
    print(f"=== CONSULTANDO PART NUMBER: {part_number} - LISTANDO 20 ANÚNCIOS ===")
    print(f"="*80)

    resultado = consultar_part_number_20_anuncios(part_number, gemini_api_key=GEMINI_API_KEY)

    if "error" not in resultado:
        print(f"\nQuery otimizada pelo Gemini Flash: {resultado['query_otimizada_gemini']}")
        print(f"Total de produtos encontrados na busca: {resultado['total_produtos_encontrados']}")
        print(f"Anúncios listados: {resultado['anuncios_listados']}")

        produto_ideal = resultado['produto_com_titulo_mais_caracteres']

        print(f"\n" + "="*80)
        print(f"=== ANÚNCIO COM TÍTULO MAIS CARACTERES ===")
        print(f"="*80)
        print(f"\nAnúncio #{produto_ideal['anuncio_numero']}")
        print(f"Título: {produto_ideal['titulo']}")
        print(f"Número de caracteres: {produto_ideal['numero_caracteres_titulo']}")
        print(f"Valor: R$ {produto_ideal['valor']} {produto_ideal['currency']}")
        print(f"Dimensões: {produto_ideal['dimensoes']}")
        print(f"Tamanho: {produto_ideal['tamanho']}")
        print(f"Largura: {produto_ideal['largura']}")
        print(f"Altura: {produto_ideal['altura']}")
        print(f"Comprimento: {produto_ideal['comprimento']}")
        print(f"Peso: {produto_ideal['peso']}")
        print(f"URL: {produto_ideal['url']}")

        # LISTAR TODOS OS 20 ANÚNCIOS
        print(f"\n" + "="*80)
        print(f"=== LISTA COMPLETA DOS 20 ANÚNCIOS ===")
        print(f"="*80)

        for anuncio in resultado['lista_20_anuncios']:
            print(f"\n{'─'*80}")
            print(f"ANÚNCIO #{anuncio['anuncio_numero']}")
            print(f"{'─'*80}")
            print(f"Título: {anuncio['titulo']}")
            print(f"Caracteres: {anuncio['numero_caracteres_titulo']} | Valor: R$ {anuncio['valor']} {anuncio['currency']}")
            print(f"Dimensões: {anuncio['dimensoes']}")
            print(f"Tamanho: {anuncio['tamanho']} | Largura: {anuncio['largura']} | Altura: {anuncio['altura']}")
            print(f"Comprimento: {anuncio['comprimento']} | Peso: {anuncio['peso']}")
            print(f"Condição: {anuncio['condition']} | Envio: {anuncio['shiping']}")
            print(f"URL: {anuncio['url']}")
            print(f"ID: {anuncio['item_id']}")

        print(f"\n" + "="*80)
        print(f"=== TOTAL: {len(resultado['lista_20_anuncios'])} ANÚNCIOS LISTADOS ===")
        print(f"="*80)
    else:
        print(f"Erro: {resultado['error']}")
        if "query_otimizada_gemini" in resultado:
            print(f"Query otimizada: {resultado['query_otimizada_gemini']}")
