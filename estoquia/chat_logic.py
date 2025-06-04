from flask import session
from datetime import datetime

def processar_mensagem(texto, usuario_id, mysql):
    resposta = ""
    partes = texto.strip().split()

    if len(partes) == 0:
        return "Desculpe, não entendi sua mensagem."

    comando = partes[0].lower()

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT nivel FROM usuarios WHERE id = %s", (usuario_id,))
    usuario = cursor.fetchone()
    nivel = usuario[0] if usuario else 'operador'

    if comando == "entrada" and len(partes) >= 3:
        nome = " ".join(partes[1:-1])
        try:
            quantidade = int(partes[-1])
            if quantidade <= 0:
                return "Quantidade inválida. Deve ser um número positivo."
            
            # Busca produto e verifica categoria conforme nivel
            cursor.execute("SELECT id, quantidade, categoria FROM produtos WHERE nome = %s", (nome,))
            produto = cursor.fetchone()
            if not produto:
                resposta = f"Produto '{nome}' não encontrado."
            else:
                produto_id, qtd_atual, categoria = produto
                # Controle de acesso por categoria
                if nivel == "limpeza" and categoria != "limpeza":
                    return "Acesso negado: você só pode acessar produtos da categoria limpeza."
                elif nivel == "operador" and categoria != "escritorio":
                    return "Acesso negado: você só pode acessar produtos da categoria escritório."
                # Limite máximo 500
                if qtd_atual + quantidade > 500:
                    return f"Limite máximo de estoque (500) ultrapassado para '{nome}'. Estoque atual: {qtd_atual}."
                cursor.execute("UPDATE produtos SET quantidade = quantidade + %s WHERE id = %s", (quantidade, produto_id))
                cursor.execute(
                    "INSERT INTO movimentacoes (produto_id, usuario_id, tipo, quantidade) VALUES (%s, %s, 'entrada', %s)",
                    (produto_id, usuario_id, quantidade)
                )
                mysql.connection.commit()
                resposta = f"Entrada de {quantidade} unidades de '{nome}' registrada."
        except ValueError:
            resposta = "Quantidade inválida."

    elif comando == "saida" and len(partes) >= 3:
        nome = " ".join(partes[1:-1])
        try:
            quantidade = int(partes[-1])
            if quantidade <= 0:
                return "Quantidade inválida. Deve ser um número positivo."

            cursor.execute("SELECT id, quantidade, categoria FROM produtos WHERE nome = %s", (nome,))
            produto = cursor.fetchone()
            if produto:
                produto_id, qtd_atual, categoria = produto
                if nivel == "limpeza" and categoria != "limpeza":
                    return "Acesso negado: você só pode acessar produtos da categoria limpeza."
                elif nivel == "operador" and categoria != "escritorio":
                    return "Acesso negado: você só pode acessar produtos da categoria escritório."
                if qtd_atual >= quantidade:
                    cursor.execute("UPDATE produtos SET quantidade = quantidade - %s WHERE id = %s", (quantidade, produto_id))
                    cursor.execute(
                        "INSERT INTO movimentacoes (produto_id, usuario_id, tipo, quantidade) VALUES (%s, %s, 'saida', %s)",
                        (produto_id, usuario_id, quantidade)
                    )
                    mysql.connection.commit()
                    resposta = f"Saída de {quantidade} unidades de '{nome}' registrada."
                else:
                    resposta = f"Estoque insuficiente ou produto '{nome}' não encontrado."
            else:
                resposta = f"Produto '{nome}' não encontrado."
        except ValueError:
            resposta = "Quantidade inválida."

    elif comando == "status" and len(partes) >= 2:
        nome = " ".join(partes[1:])
        cursor.execute("SELECT quantidade, limite_estoque, categoria FROM produtos WHERE nome = %s", (nome,))
        resultado = cursor.fetchone()
        if resultado:
            quantidade, limite, categoria = resultado
            if nivel == "limpeza" and categoria != "limpeza":
                return "Acesso negado: você só pode acessar produtos da categoria limpeza."
            elif nivel == "operador" and categoria != "escritorio":
                return "Acesso negado: você só pode acessar produtos da categoria escritório."
            alerta = " ⚠️ Estoque abaixo do limite!" if quantidade <= limite else ""
            resposta = f"O estoque atual de '{nome}' é {quantidade} unidades.{alerta}"
        else:
            resposta = f"Produto '{nome}' não encontrado."

    elif comando == "listar":
        if nivel == "admin":
            cursor.execute("SELECT categoria, nome, quantidade, limite_estoque FROM produtos ORDER BY categoria, nome")
        elif nivel == "limpeza":
            cursor.execute("SELECT categoria, nome, quantidade, limite_estoque FROM produtos WHERE categoria = 'limpeza' ORDER BY nome")
        elif nivel == "operador":
            cursor.execute("SELECT categoria, nome, quantidade, limite_estoque FROM produtos WHERE categoria = 'escritorio' ORDER BY nome")
        produtos = cursor.fetchall()
        if produtos:
            resposta = ""
            categoria_atual = None
            for categoria, nome, qtd, limite in produtos:
                if nivel == "admin":
                    if categoria != categoria_atual:
                        categoria_atual = categoria
                        resposta += f"\nCategoria: {categoria_atual}\n"
                alerta = " ⚠️ Baixo estoque!" if qtd <= limite else ""
                resposta += f"- {nome}: {qtd}{alerta}\n"
        else:
            resposta = "Nenhum produto cadastrado."

    elif comando == "cadastrar" and len(partes) >= 5:
        if nivel != "admin":
            resposta = "Acesso negado: apenas administradores podem cadastrar produtos."
        else:
            try:
                # Quantidade, limite e categoria são as 3 últimas palavras, nome é o resto
                quantidade = int(partes[-3])
                limite = int(partes[-2])
                categoria = partes[-1].lower()
                nome = " ".join(partes[1:-3])

                if quantidade < 0 or limite < 0:
                    return "Quantidade e limite devem ser números positivos."

                if quantidade > 500:
                    return "Quantidade inicial não pode ser maior que 500."

                if limite > 500:
                    return "Limite máximo permitido é 500."

                cursor.execute("SELECT id FROM produtos WHERE nome = %s", (nome,))
                existente = cursor.fetchone()
                if existente:
                    resposta = f"Produto '{nome}' já existe."
                else:
                    cursor.execute(
                        "INSERT INTO produtos (nome, quantidade, limite_estoque, categoria) VALUES (%s, %s, %s, %s)",
                        (nome, quantidade, limite, categoria)
                    )
                    mysql.connection.commit()
                    resposta = (
                        f"Produto '{nome}' cadastrado com {quantidade} unidades, "
                        f"limite mínimo de {limite} unidades e categoria '{categoria}'."
                    )
            except ValueError:
                resposta = "Formato inválido. Use: cadastrar nome quantidade limite categoria"

    elif comando == "adicionarusuario" and len(partes) in [4, 5]:
        if nivel != "admin":
            resposta = "Apenas administradores podem adicionar novos usuários."
        else:
            nome, email, senha = partes[1], partes[2], partes[3]
            novo_nivel = partes[4].lower() if len(partes) == 5 else "operador"

            if novo_nivel not in ["admin", "operador", "limpeza"]:
                resposta = "Nível inválido. Use 'admin', 'operador' ou 'limpeza'."
            else:
                cursor.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
                existente = cursor.fetchone()
                if existente:
                    resposta = f"Já existe um usuário com o e-mail '{email}'."
                else:
                    cursor.execute(
                        "INSERT INTO usuarios (nome, email, senha, nivel) VALUES (%s, %s, %s, %s)",
                        (nome, email, senha, novo_nivel))
                    mysql.connection.commit()
                    resposta = f"Usuário '{nome}' cadastrado como {novo_nivel} com sucesso."

    elif comando == "excluirusuario" and len(partes) == 2:
        if nivel != "admin":
            resposta = "Apenas administradores podem excluir usuários."
        else:
            email = partes[1]
            cursor.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
            resultado = cursor.fetchone()
            if not resultado:
                resposta = f"Usuário com e-mail '{email}' não encontrado."
            elif resultado[0] == usuario_id:
                resposta = "Você não pode excluir a si mesmo."
            else:
                usuario_excluir_id = resultado[0]

                cursor.execute("DELETE FROM mensagens WHERE usuario_id = %s", (usuario_excluir_id,))
                cursor.execute("DELETE FROM usuarios WHERE id = %s", (usuario_excluir_id,))
                mysql.connection.commit()
                resposta = f"Usuário '{email}' e suas mensagens foram excluídos com sucesso."

    elif comando == "comandos":
        resposta = (
            "Comandos disponíveis:\n"
            "- entrada nome quantidade\n"
            "- saida nome quantidade\n"
            "- status nome\n"
            "- listar\n"
            "- cadastrar nome quantidade limite categoria (admin)\n"
            "- adicionarusuario nome email senha nivel (admin)\n"
            "- comandos"
        )

    else:
        resposta = (
            "Comando não reconhecido. Use:\n"
            "- entrada nome quantidade\n"
            "- saida nome quantidade\n"
            "- status nome\n"
            "- listar\n"
            "- cadastrar nome quantidade limite categoria (admin)\n"
            "- adicionarusuario nome email senha nivel (admin)\n"
            "- comandos"
        )

    cursor.execute("INSERT INTO mensagens (usuario_id, remetente, mensagem) VALUES (%s, 'usuario', %s)", (usuario_id, texto))
    cursor.execute("INSERT INTO mensagens (usuario_id, remetente, mensagem) VALUES (%s, 'bot', %s)", (usuario_id, resposta))
    mysql.connection.commit()

    return resposta
