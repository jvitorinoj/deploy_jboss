#!/usr/bin/env /usr/bin/python3
# -*- coding: UTF-8 -*-
__author__ = 'joao.vitorino'
'''
Data de criacao: 16/05/17
Descricao: Realiza deploy no Jboss 7. Script eh executado através de job no Jenkins \
    1 - Verifica se o pacote informado ja existe em algum server-group   \
    2 - Caso positivo realiza undeploy \
    3 - Caso negativo verifica se existe no content do jboss, se sim faz o undeploy se nao faz o deploy \
    TODO - Verificar se a aplicação está rodando \
    TODO - Criar uma lista com os server-groups encontrados no servidor
'''

import os
import requests
import sys
from requests.auth import HTTPDigestAuth
import argparse



parser = argparse.ArgumentParser(prog="Jboss 7 Deploy",usage='pyhton deploy_jboss_7.py --pacote /path/PackgeName.war --host Jboss_server_name  --user JBoss_user --pass JBoss_pass --group Server_group',description='Realiza deploy e redeploy.')
parser.add_argument('--pacote',action='store',dest='pacote_path',help='nome do pacote a ser feito deploy com ou sem path',required=True)
parser.add_argument('--host',action='store',dest='srv_nome',help='nome do servidor jboss',required=True)
parser.add_argument('--user',action='store',dest='srv_login',help='usuario do jboss',required=True)
parser.add_argument('--pass',action='store',dest='srv_senha',help='senha do usuario do jboss',required=True)
parser.add_argument('--group',action='store',dest='srv_grupo',help='nome do server group a ser feito o deploy')

args = parser.parse_args()
srv_login = args.srv_login
srv_senha = args.srv_senha
srv_nome = args.srv_nome
srv_grupo = args.srv_grupo
pacote_path = args.pacote_path

srv_porta='9990'
srv_url='http://{0}:{1}/management'.format(srv_nome,srv_porta)
timeout = 300
lista_srv_grupos = ['serverGrupoA','webServices','serverGrupoB']
grupos_encontrados = []

# Verifica se arquivo existe
if os.path.exists(pacote_path) == True:
    pass
else:
    sys.exit("Arquivo {} nao encontrado".format(pacote_path))

# Separa nome do pacote do seu path
if "\\" in pacote_path:
    pacote = args.pacote_path.rsplit("\\")[-1]
elif "/" in pacote_path:
    pacote = args.pacote_path.rsplit("/")[-1]
else:
    pacote = args.pacote_path


#Configura opcoes comuns de todas as requisicoes http
url_ = requests.Session()
url_.auth = HTTPDigestAuth(srv_login,srv_senha)
url_.headers = {'Content-Type': 'application/json'}

# Inicio declaracao de funcoes
# TODO: Funcao para verificar quais os server-groups disponiveis no Jboss

# Funcao para fazer as requisicaoes via post ao servidor do jboss
def req_http(json_data):
    http_resposta = url_.post(srv_url, json=json_data,timeout=timeout)
    return http_resposta

# Retorna erro e finaliza se http response code for diferente de 200 ou resposta do jboss = failed
def erro(requisicao):
    if requisicao.json()['outcome'] == 'failed':
        print('Servidor {0} retornou código {1} ou um erro inesperado'.format(srv_nome,requisicao.status_code))
        print('Cancelando operacao')
        print('Erro retornado {0}'.format(requisicao.json()))
        exit(1)
    else:
        return False


def deploy():
    url = srv_url + '/add-content'
    print('Realizando o upload do arquivo {0}'.format(pacote))
    files = {'file': open(pacote_path, 'rb')}
    upload = requests.post(url=url, auth=HTTPDigestAuth(srv_login, srv_senha), files=files)
    upload_resposta = upload.json()
    if erro(upload) == False:
        if upload_resposta['outcome'] == 'success':
            print('>>>>> Upload do pacote realizado com sucesso')
            print('>>>>> Habilitando o pacote no Jboss')
            habilitar_data, appHash, content = ({}, {}, {})
            appHash["BYTES_VALUE"] = upload_resposta['result']['BYTES_VALUE']
            content['hash'] = appHash
            habilitar_data['content'] = [content]
            habilitar_data['address'] = ([{'deployment': pacote}])
            habilitar_data['operation'] = 'add'
            habilitar_data['enabled'] = 'true'
            r_habilitar = req_http(habilitar_data)
            if erro(r_habilitar) == False:
                print('Pacote {0} habilitado no \'Content Repository\' do Jboss com sucesso'.format(pacote))
                print('Realizando assign')
                assign_data = {"operation": "add"}
                address = [{"server-group": srv_grupo}, {"deployment": pacote}]
                assign_data['address'] = address
                assign_data['runtime-name'] = pacote
                assign_data['enabled'] = 'true'
                assign = req_http(assign_data)
                if erro(assign) == False:
                    print('>>>>>Assign realizado com sucesso no server-group: {0}'.format(srv_grupo))
                    return True



# Funcao para realizar o unassign do pacote em todos os server-groups encontrados
def unassign(s_groups):
    # Montagem do comando json para realizar o unassign
    unassign_data = {'operation': 'remove'}
    for k in s_groups:
        print('Realizando unassign do pacote {0} em {1}'.format(pacote,k))
        # Montagem do comando json para realizar o unassign
        address = [{"server-group": k}, {"deployment": pacote}]
        unassign_data['address'] = address
        unassign = req_http(unassign_data)
        unassign_resultado = unassign.json()
        if erro(unassign) == False:
            if unassign_resultado['outcome'] == 'success':
                print('Removido do server-group {0} com sucesso'.format(k))
            else:
                print('Remocao do pacote do server-group {0} FALHOU'.format(k))
                print('Cancelando operacao')
                print('Erro retornado {0}'.format(unassign_resultado.json()))
                exit(1)
    return True

# Remove o pacote do Content Repository
def remove():
    remove_data = {"operation": "remove"}
    address = [{"deployment": pacote}]
    remove_data['address'] = address
    remove = req_http(remove_data)
    if erro(remove) == False:
        if remove.json()['outcome'] == 'success':
            return True # Pacote removido com sucesso
        else:
            print('Cancelando operacao')
            print('Erro retornado {0}'.format(remove.json()))
            exit(1)

# Verifica se pacote existe no Content Repository
# Se o pacote existe em algum server-group (funcao associado_grupo) ele nao precisa ser verificado aqui
def ver_content():
    ver_content_data = {"operation": "read-resource"}
    address = [{"deployment": pacote}]
    ver_content_data['address'] = address
    content = req_http(ver_content_data)
    if content.json()['outcome'] == 'success' and content.json()['result']['name'] == pacote:
        return True # Pacote existe no content repository
    else:
        return False #Pacote nao encontrado



# Verifica se o pacote esta associado a algum server-group
def associado_grupo(): # Verifica se o pacote está associado a algum server
    checa_data = {"operation": "read-resource"}
    address = {"server-group": "*"}, {"deployment": pacote}
    checa_data['address'] = address
    checa_grupo = req_http(checa_data)
    if erro(checa_grupo) == False:
        return checa_grupo

# Fim da declaracao de funcoes


# Inicio da execucao do script. Verificar se o pacote ja existe em algum server group
checa_pacote = str(associado_grupo().json())

# noinspection PyUnboundLocalVariable
if checa_pacote.find(pacote) == -1: # se o pacote nao existir em nenhum server-group
    print('Pacote {0} não associado a nenhum server-group.'.format(pacote))
    print('Verificando se pacote existe no \'Content Repository\' do Jboss')
    if ver_content() == False:
        print('Pacote inexistente, realizando deploy')
        deploy()
    else:
        print('Pacote encontrado no \'Content Repository\', realizando undeploy')
        remove() #Tratamento de erro esta dentro da funcao remove
        deploy()

else: # Pacote existe em pelo menos 1 server-group
    for g in lista_srv_grupos:
        if g in str(checa_pacote):
            grupos_encontrados.append(g) #  Cria lista contento todos os server-groups em que o pacote existe
    print('Pacote encontrado nos seguintes server-groups \'{0}\', realizando unassign'.format(grupos_encontrados))
    if unassign(grupos_encontrados) == True:
        remove()
        deploy()

exit(0)
