# MotorMind - Django Templates + Tailwind CSS + DaisyUI

## v37 - Fase de deploy na VPS Hostinger

Alteracoes incluidas nesta entrega:

- Adicionada documentacao completa de deploy para VPS Linux da Hostinger em `docs/DEPLOY_HOSTINGER_VPS.md`.
- Adicionada pasta `deploy/` com:
  - template de Nginx;
  - unit file do systemd para Gunicorn;
  - script de bootstrap da VPS;
  - script de instalacao/atualizacao de release;
  - script de instalacao dos servicos do sistema;
  - script de backup do SQLite e da pasta `media/`.
- Adicionado `.env.production.example` com variaveis seguras para producao.
- Adicionado `gunicorn` ao `requirements.txt`.
- Ajustado `config/settings.py` para aceitar variaveis de producao:
  - `CSRF_TRUSTED_ORIGINS`;
  - `SECURE_PROXY_SSL_HEADER`;
  - `USE_X_FORWARDED_HOST`;
  - `SECURE_SSL_REDIRECT`;
  - `SESSION_COOKIE_SECURE`;
  - `CSRF_COOKIE_SECURE`;
  - `SECURE_HSTS_SECONDS`;
  - `DB_ENGINE`;
  - `DB_NAME`;
  - `DB_USER`;
  - `DB_PASSWORD`;
  - `DB_HOST`;
  - `DB_PORT`.
- Adicionado endpoint publico de saude:

```txt
/healthz/
```

Fluxo recomendado na VPS:

```bash
sudo bash deploy/scripts/bootstrap_hostinger_vps.sh
cd /var/www/motormind/current
sudo cp .env.production.example .env
sudo nano .env
sudo bash deploy/scripts/install_or_update_release.sh
sudo bash deploy/scripts/install_system_services.sh seudominio.com
```

Depois crie o usuario administrador:

```bash
sudo -u motormind /var/www/motormind/current/.venv/bin/python /var/www/motormind/current/manage.py createsuperuser
```

Valide a aplicacao:

```bash
curl http://127.0.0.1:8001/healthz/
sudo systemctl status motormind
```

Comandos de validacao executados nesta versao:

```bash
python manage.py check
python manage.py migrate --noinput
python manage.py setup_roles
python manage.py makemigrations --check --dry-run
python -m compileall -q accounts ai_assistant core communications config stock operations manage.py
npm install
npm run css:build
```


## v37 - Módulo de IA para OS e mensagens

Alterações incluídas nesta entrega:

- Criado app `ai_assistant` para centralizar configurações, integrações e logs de uso de IA.
- Configuração pelo **Admin Django** e pelo menu **Configurações > IA**.
- Provedores configuráveis:
  - Local / simulado, para desenvolvimento sem chave externa;
  - OpenAI;
  - Anthropic;
  - Google Gemini;
  - Ollama;
  - Endpoint customizado.
- Campos configuráveis:
  - IA ativa/inativa;
  - provedor;
  - modelo;
  - chave de API;
  - endpoint/base URL;
  - temperatura;
  - timeout;
  - tom da resposta;
  - características da oficina;
  - instruções gerais;
  - limite aproximado de caracteres;
  - exibir IA em OS;
  - exibir IA em mensagens/templates.
- Botão **Testar conexão da IA** na tela de configuração.
- Botões pequenos de IA próximos aos campos da OS:
  - problema relatado: **IA melhorar**;
  - diagnóstico: **IA detalhar**;
  - observação: **Sugerir obs.**.
- Botões de IA em templates e mensagem manual:
  - **IA melhorar**;
  - **Gerar email**;
  - **Gerar WhatsApp**.
- O texto gerado substitui diretamente o conteúdo do campo de destino.
- Criado log de uso de IA com ação, provedor, modelo, entrada, contexto, resposta, sucesso/erro e usuário.
- Nova rota de configuração:

```txt
/configuracoes/ia/
```

- Novas rotas internas de IA:

```txt
/configuracoes/ia/testar/
/ia/assistir-texto/
```

- Nova migration:

```txt
ai_assistant/migrations/0001_initial.py
```

Comandos para atualizar:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
python manage.py migrate
python manage.py setup_roles
python manage.py check
npm run css:build
python manage.py runserver
```

Validações executadas nesta versão:

```bash
python manage.py check
python manage.py migrate --noinput
python manage.py setup_roles
python manage.py makemigrations --check --dry-run
python -m compileall -q accounts ai_assistant core communications config stock operations manage.py
npm install
npm run css:build
```

Também foi validado via Django Client:

- renderização de `/configuracoes/ia/`;
- renderização da criação de OS com botões de IA;
- renderização de templates de mensagem com botões de IA;
- renderização de mensagem manual com botões de IA;
- endpoint `/ia/assistir-texto/` com provedor local;
- endpoint `/configuracoes/ia/testar/` com provedor local.

## v37 - Aprovação formal e orçamento versionado da OS

Alterações incluídas:

- Implementado fluxo formal de aprovação de orçamento da OS como orçamento versionado.
- Ao mover a OS para **Aguardando aprovação**, o sistema cria uma nova versão de orçamento e congela um snapshot dos serviços, combos e peças/insumos atuais.
- O snapshot inclui valores unitários, quantidades, subtotais, desconto e total do orçamento no momento do envio.
- Envio de email de orçamento ao cliente com link público por token.
- Novo tipo de template no Centro de Mensagens: **Orçamento / aprovação da OS**.
- Página pública `/aprovacao-os/<token>/` para o cliente responder ao orçamento.
- O cliente pode:
  - aprovar tudo;
  - aprovar parcialmente;
  - recusar tudo.
- Na aprovação parcial, a interface exibe aviso antes da confirmação e permite prosseguir.
- A observação do formulário já vem preenchida com **Aprovado**.
- Resposta pública exige nome, CPF/CNPJ válido e observação.
- Registro interno de aprovação com métodos:
  - email;
  - WhatsApp;
  - cliente presencialmente;
  - oficina.
- Auditoria da aprovação registra:
  - quem aprovou/recusou;
  - documento válido informado;
  - data/hora;
  - local;
  - IP;
  - user agent;
  - usuário interno, quando a aprovação for registrada pela oficina;
  - observação;
  - itens aprovados e rejeitados no snapshot.
- Após aprovação total ou parcial, a OS passa a considerar financeiramente e para estoque apenas os itens aprovados.
- Itens não aprovados permanecem no orçamento versionado para rastreabilidade.
- Serviços, combos e peças com orçamento em aprovação ou aprovado ficam bloqueados para edição direta.
- Para alterar itens depois de aprovação ou durante aprovação, use **Gerar novo orçamento**, que substitui a versão anterior e retorna a OS para revisão de orçamento.
- Adicionados botões/ações na OS:
  - **Enviar orçamento**;
  - **Registrar aprovação**;
  - **Gerar novo orçamento**;
  - detalhe do orçamento versionado.

Novas rotas:

```txt
/operacional/os/<id>/enviar-orcamento/
/operacional/os/<id>/registrar-aprovacao/
/operacional/os/<id>/novo-orcamento/
/operacional/aprovacoes/<id>/
/aprovacao-os/<token>/
```

Novas migrations:

```txt
operations/migrations/0011_work_order_approvals.py
communications/migrations/0005_work_order_approval_messages.py
```

Comandos para atualizar:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
python manage.py migrate
python manage.py setup_roles
python manage.py check
npm run css:build
python manage.py runserver
```

Validações executadas nesta versão:

```bash
python manage.py migrate --noinput
python manage.py setup_roles
python manage.py check
python manage.py makemigrations --check --dry-run
python -m compileall -q accounts core communications config stock operations manage.py
node --check static/js/work-order-items.js
node --check static/js/work-order-form.js
npm run css:build
```

Também foi validado via shell Django e Client:

- criação automática do orçamento v1 ao mover a OS para **Aguardando aprovação**;
- envio de email de orçamento com link público por token;
- renderização da tela pública de aprovação;
- renderização da tela interna de registro de aprovação;
- renderização do detalhe do orçamento versionado;
- aprovação parcial mantendo itens rejeitados no snapshot;
- OS aprovada considerando somente itens aprovados no total financeiro e nos requisitos de estoque;
- bloqueio de edição direta enquanto houver orçamento pendente/aprovado;
- liberação para revisão após **Gerar novo orçamento**.

## v32 - Quantidade ajustável de peças previstas da OS e bloqueio real de campos sensíveis

Alterações incluídas:

- Criado ajuste de quantidade das peças previstas por OS.
- Peças padrão vindas de serviço ou combo agora podem ter quantidade ajustada naquela OS específica.
- Exemplo: se o combo prevê 4L de óleo, a OS pode ser ajustada para 3L ou 5L.
- A quantidade ajustada passa a ser usada em:
  - validação de estoque;
  - bloqueio de início do serviço;
  - baixa automática de estoque;
  - mensagem de falta de estoque.
- A tela de detalhe da OS permite editar as quantidades previstas quando o estoque ainda não foi baixado.
- A tela da mecânica também permite editar as quantidades previstas quando o estoque ainda não foi baixado.
- A quantidade padrão continua visível para comparação.
- Quando a quantidade ajustada for igual à quantidade padrão, o ajuste é removido automaticamente.
- Ajustes antigos de peças que deixam de existir na OS são descartados automaticamente.
- Reforçado o bloqueio backend dos campos sensíveis da OS após a abertura:
  - cliente;
  - veículo;
  - KM atual;
  - previsão de entrega;
  - problema relatado.
- Mesmo que alguém tente alterar esses campos via POST manual, o sistema preserva os valores originais da OS.
- O formulário de edição agora usa sempre o cliente original da OS para montar a lista de veículos, evitando troca indevida por manipulação de request.

Nova migration:

```txt
operations/migrations/0009_workorder_stock_requirement_overrides.py
```

Comandos para atualizar:

```bash
python manage.py migrate
python manage.py setup_roles
python manage.py check
npm install
npm run css:build
python manage.py runserver
```

Validações executadas nesta versão:

```bash
python manage.py migrate --noinput
python manage.py setup_roles
python manage.py check
python manage.py makemigrations --check --dry-run
python -m compileall -q accounts core communications config stock operations manage.py
node --check static/js/work-order-items.js
npm run css:build
```

Também foi validado via shell Django:

- combo com serviço que exige 4 unidades de peça gera requisito base 4;
- ajuste da OS para 5 unidades muda a validação de estoque para 5;
- ajuste pela tela para 3 unidades é salvo e usado na OS;
- POST malicioso tentando trocar cliente, veículo, KM, previsão e problema relatado não altera esses campos;
- detalhes da OS e tela da mecânica renderizam com as novas quantidades ajustáveis.



## Versão v30

- A fila da mecânica agora também exibe OS em **Aberta** e **Diagnóstico**.
- Técnicos podem abrir o detalhe mecânico dessas OS e acrescentar serviços, combos e peças conforme necessidade.
- O botão **Dar início ao serviço** continua restrito a OS **Aprovada** ou **Aguardando peça**.
- OS com peça sem estoque suficiente continuam impedidas de entrar em **Em execução**.

## v28 - Máquina de estados da OS aderente ao fluxo real da oficina

Esta versão ajusta a máquina de estados da OS para seguir o cronograma operacional de uma oficina mecânica.

### Fluxo principal

```txt
Aberta -> Diagnóstico -> Orçamento -> Aguardando aprovação -> Aprovada -> Em execução -> Em teste -> Pronta -> Pronto para retirar -> Entregue -> Arquivada
```

### Estados disponíveis

- Aberta: recepção, abertura da OS e registro inicial do problema.
- Diagnóstico: avaliação inicial e identificação técnica do problema.
- Orçamento: composição de serviços, peças, combos e valores estimados.
- Aguardando aprovação: orçamento enviado ao cliente e pendente de aceite.
- Aprovada: cliente aprovou a execução.
- Em execução: serviço em andamento.
- Aguardando peça: pausa operacional por dependência de estoque/compra.
- Em teste: teste e verificação final antes da conclusão interna.
- Pronta: serviço concluído internamente.
- Pronto para retirar: cliente já pode retirar o veículo.
- Entregue: veículo retirado pelo cliente.
- Cancelada: OS encerrada sem execução/conclusão.
- Arquivada: encerramento administrativo após entrega ou cancelamento.

### Ajustes técnicos

- OS nova agora inicia como `Aberta`.
- `Orçamento` foi reposicionado para depois de `Diagnóstico`.
- Incluídos os estados `Em teste` e `Arquivada`.
- Transições inválidas continuam bloqueadas pela máquina de estados.
- Baixa de estoque agora também é permitida no estado `Em teste`.
- A tela de detalhe da OS mostra o novo fluxo principal.

Para atualizar:

```bash
python manage.py migrate
python manage.py setup_roles
python manage.py check
npm install
npm run css:build
python manage.py runserver
```


### v27 - Máquina de estados da OS

- A OS agora usa máquina de estados com transições válidas e auditáveis.
- Estados implementados: **Orçamento**, **Diagnóstico**, **Aguardando aprovação**, **Aprovada**, **Em execução**, **Aguardando peça**, **Pronta**, **Pronto para retirar**, **Entregue** e **Cancelada**.
- Estados sugeridos adicionados por consistência operacional:
  - **Entregue**: diferencia veículo pronto de veículo realmente retirado pelo cliente.
  - **Cancelada**: encerra uma OS interrompida sem conclusão operacional.
- Fluxo principal: `Orçamento -> Diagnóstico -> Aguardando aprovação -> Aprovada -> Em execução -> Pronta -> Pronto para retirar -> Entregue`.
- A OS pode ir para **Aguardando peça** durante diagnóstico, aprovação ou execução.
- **Entregue** e **Cancelada** são estados terminais.
- A tela de detalhe da OS mostra os próximos status permitidos e histórico de transições.
- Alterações diretas no formulário da OS também respeitam a máquina de estados.
- Migração de status antigos:
  - `aberta` -> `diagnostico`
  - `aguardando_pecas` -> `aguardando_peca`
  - `finalizada` -> `pronta`


### v25 - Fotos múltiplas no check-in

- O check-in agora permite adicionar várias fotos em uma mesma operação.
- No celular/tablet, o botão **Adicionar outra foto** abre novamente a câmera para anexar mais imagens.
- Todas as fotos novas são preservadas ao editar o check-in, sem apagar fotos já cadastradas.
- O PDF do check-in renderiza todas as fotos anexadas.

# MotorMind Django Templates + Tailwind CSS + DaisyUI

Starter Django com:

- Login de funcionários e superusuário usando **email como username**.
- Superusuário com acesso total, inclusive ao `/admin/` do Django.
- Funcionários separados por perfil: administrativo, atendente, técnico, financeiro e estoque.
- Clientes e fornecedores **sem herdar `User`** e sem acesso ao sistema.
- Cliente novo inicia como **pessoa física**.
- Fornecedor novo inicia como **pessoa jurídica**.
- Categorias aplicáveis a cliente ou fornecedor.
- Categorias de cliente e fornecedor renderizadas como checkboxes para evitar quebra visual do campo.
- Cadastros com pessoa física/jurídica, nome/razão social, email obrigatório, WhatsApp, endereço opcional com busca por CEP e aceite de marketing.
- CPF/CNPJ e data de nascimento/fundação são opcionais para clientes e fornecedores.
- Campo de data com placeholder usando o dia atual no formato `YYYY-MM-DD`.
- Alerta de duplicidade para email e telefone/WhatsApp dentro do mesmo tipo de cadastro; cliente e fornecedor podem compartilhar email e telefone. Documento continua validado quando informado.
- Máscaras de CPF, CNPJ, telefone/WhatsApp e CEP no frontend.
- Exclusão lógica para clientes, fornecedores e categorias.
- Páginas de listagem, cadastro, edição, exclusão lógica e visualização de clientes e fornecedores.
- Listagens de clientes e fornecedores sem documento nem data de nascimento/fundação, mantendo esses dados na visualização.
- Listagens de categorias e funcionários sem coluna de status.
- Menu principal organizado em Atendimento, Estoque, Mensagens e Configurações, com submenus.
- Configurações de mensagens para habilitar/desabilitar independentemente envio automático para pessoa física e pessoa jurídica.
- Mensagem manual por email para clientes, fornecedores, categorias de clientes, categorias de fornecedores ou todos.
- Histórico de mensagens com status **Enviado**, **Erro** ou **Pendente**.
- Envio automático de email de aniversário/fundação para clientes com data preenchida.
- Templates de mensagens editáveis pelo sistema, incluindo aniversário de pessoa física, fundação de pessoa jurídica e comunicados manuais.
- Cadastros de categorias e templates de mensagens sem campo de status/ativo para o usuário.
- Mensagens do sistema exibidas como alertas flutuantes, com desaparecimento automático e maior permanência para erros.
- Sistema de peças e insumos com SKU automático, categoria global, marca, unidade normalizada, estoque mínimo e preço de custo.
- Busca avançada de peças/insumos com autocomplete, filtros por tipo, categoria, marca, unidade, situação de estoque e faixa de custo, além de botão para limpar filtros.
- Busca simples com autocomplete nas listagens de categorias e funcionários, com botão para limpar filtros.
- Cadastro de marcas em Configurações.
- Cadastro de categorias globais de estoque em Configurações.
- Unidades de medida normalizadas em tabela própria e carregadas por migration.
- Campos monetários tratados pelo core `core.money`, sempre com duas casas decimais.
- Movimentações de estoque para entrada, saída, ajuste positivo e ajuste negativo, preservando histórico e saldo após movimentação.
- Templates Django com Tailwind CSS + DaisyUI.
- Sistema de OS com máquina de estados, transições controladas e histórico de alterações de status.

## Requisitos

- Python 3.11+
- Node.js 20+

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
```

No Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
npm install
```

## Configuração

```bash
cp .env.example .env
```

No Windows PowerShell:

```powershell
copy .env.example .env
```

Em desenvolvimento, o backend de email padrão imprime as mensagens no console:

```env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=MotorMind <no-reply@localhost>
```

Para envio real por SMTP, configure no `.env`:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.seudominio.com
EMAIL_PORT=587
EMAIL_HOST_USER=usuario@seudominio.com
EMAIL_HOST_PASSWORD=sua-senha
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=MotorMind <usuario@seudominio.com>
```

## Banco de dados e permissões

Em projeto novo:

```bash
python manage.py migrate
python manage.py setup_roles
python manage.py createsuperuser
```

Em um projeto que já estava rodando a versão anterior:

```bash
python manage.py migrate
python manage.py setup_roles
python manage.py check
```

O `createsuperuser` pedirá **email** em vez de username.

## Tailwind CSS + DaisyUI

Gerar CSS uma vez:

```bash
npm run css:build
```

Durante o desenvolvimento, deixe o Tailwind observando alterações:

```bash
npm run css:watch
```

Em outro terminal, rode o Django:

```bash
python manage.py runserver
```

Ou rode Django + watcher juntos:

```bash
npm run dev
```

## Menus

- **Atendimento**
  - Clientes
- **Estoque**
  - Peças e insumos
  - Movimentações
  - Fornecedores
- **Mensagens**
  - Mensagem manual
  - Templates
  - Histórico de mensagens
- **Configurações**
  - Categorias
  - Funcionários
  - Categorias de estoque
  - Marcas
  - Mensagens
  - Admin Django, quando o usuário for superusuário

## Rotas principais

- `/login/` — login por email
- `/logout/` — logout
- `/dashboard/` — painel interno
- `/clientes/` — listagem de clientes ativos
- `/clientes/novo/` — cadastro de cliente, iniciando como pessoa física
- `/clientes/<id>/` — visualização de cliente
- `/clientes/<id>/editar/` — edição de cliente
- `/clientes/<id>/excluir/` — exclusão lógica de cliente
- `/fornecedores/` — listagem de fornecedores ativos
- `/fornecedores/novo/` — cadastro de fornecedor, iniciando como pessoa jurídica
- `/fornecedores/<id>/` — visualização de fornecedor
- `/fornecedores/<id>/editar/` — edição de fornecedor
- `/fornecedores/<id>/excluir/` — exclusão lógica de fornecedor
- `/categorias/` — CRUD de categorias de clientes/fornecedores não excluídas, com busca simples e autocomplete
- `/categorias/autocomplete/` — endpoint JSON de autocomplete para categorias
- `/funcionarios/` — CRUD de funcionários, com busca simples e autocomplete
- `/funcionarios/autocomplete/` — endpoint JSON de autocomplete para funcionários
- `/estoque/itens/` — listagem de peças e insumos ativos, com busca avançada e ordenação A-Z por nome
- `/estoque/itens/autocomplete/` — endpoint JSON de autocomplete para peças e insumos
- `/estoque/itens/novo/` — cadastro de peça/insumo com SKU automático
- `/estoque/itens/<id>/` — visualização de peça/insumo com saldo e últimas movimentações
- `/estoque/itens/<id>/editar/` — edição de peça/insumo
- `/estoque/itens/<id>/excluir/` — exclusão lógica de peça/insumo
- `/estoque/movimentacoes/` — histórico de movimentações de estoque com busca avançada
- `/estoque/movimentacoes/autocomplete/` — endpoint JSON de autocomplete para movimentações de estoque
- `/estoque/movimentacoes/nova/` — entrada, saída ou ajuste de estoque
- `/estoque/movimentacoes/<id>/` — detalhe da movimentação de estoque
- `/configuracoes/estoque/categorias/` — CRUD de categorias globais de estoque
- `/configuracoes/marcas/` — CRUD de marcas
- `/configuracoes/mensagens/` — configurações dos envios automáticos de mensagens
- `/mensagens/manual/` — envio manual de email
- `/mensagens/templates/` — listagem de templates de mensagens
- `/mensagens/templates/novo/` — criação de template de mensagem
- `/mensagens/templates/<id>/editar/` — edição de template de mensagem
- `/mensagens/templates/<id>/excluir/` — exclusão lógica de template de mensagem
- `/mensagens/historico/` — histórico de emails enviados ou com erro
- `/admin/` — admin Django, apenas para superusuário/staff

## Mensagens manuais

A tela `/mensagens/manual/` permite selecionar destinatários por:

- um ou mais clientes;
- um ou mais fornecedores;
- uma ou mais categorias de clientes;
- uma ou mais categorias de fornecedores;
- todos os clientes e fornecedores ativos.

A opção **Enviar somente para contatos que aceitam marketing** pode ser marcada para filtrar apenas contatos com aceite.

Cada destinatário gera um registro em `MessageLog`, com status enviado ou erro.

A tela permite selecionar um template existente. Ao selecionar, o assunto e o corpo são preenchidos automaticamente, podendo ser ajustados antes do envio.

## Templates de mensagens

A tela `/mensagens/templates/` permite criar e editar modelos reutilizáveis de email. Existem três tipos iniciais:

- **Aniversário - Cliente pessoa física**: usado pelo envio automático de aniversário.
- **Fundação - Cliente pessoa jurídica**: usado pelo envio automático da data de fundação.
- **Manual / Outro**: usado em mensagens manuais, campanhas e comunicados.

Os templates aceitam HTML simples e variáveis do template engine do Django, por exemplo:

```django
{{ nome }}
{{ email }}
{{ data_envio }}
{{ cliente.nome_razao_social }}
{{ fornecedor.nome_razao_social }}
{{ destinatario.nome_razao_social }}
```

Para aniversário/fundação, marque o template desejado como **Template padrão?**. O sistema permite apenas um padrão por tipo entre os templates não excluídos.

## Configurações de mensagens

A tela `/configuracoes/mensagens/` fica dentro do menu **Configurações > Mensagens** e controla os envios automáticos de aniversário/fundação.

As opções são independentes:

- habilitar somente aniversário de pessoa física;
- habilitar somente fundação de pessoa jurídica;
- habilitar ambos;
- desabilitar ambos.

Quando o comando `python manage.py send_anniversary_emails` é executado, ele verifica essas flags antes de selecionar os clientes. Se uma opção estiver desabilitada, o comando mostra uma mensagem de erro no console e ignora aquele tipo de envio.

## Emails automáticos de aniversário/fundação

O comando abaixo envia emails para clientes ativos cuja data de nascimento/fundação tenha o mesmo dia e mês da data de execução:

```bash
python manage.py send_anniversary_emails
```

Testar sem enviar nem gravar histórico:

```bash
python manage.py send_anniversary_emails --dry-run
```

Processar uma data específica:

```bash
python manage.py send_anniversary_emails --date 2026-06-03
```

O comando diferencia automaticamente:

- **Pessoa física**: usa template de aniversário.
- **Pessoa jurídica**: usa template de fundação.


Antes de selecionar os clientes, o comando verifica as configurações em **Configurações > Mensagens**:

- se aniversário de pessoa física estiver desabilitado, clientes pessoa física são ignorados e o console mostra erro;
- se fundação de pessoa jurídica estiver desabilitado, clientes pessoa jurídica são ignorados e o console mostra erro;
- se ambos estiverem desabilitados, nenhum envio automático é processado.

Os templates usados pelo envio automático são lidos do banco de dados em `MessageTemplate`. A migration `communications.0002` cria templates iniciais para aniversário de pessoa física, fundação de pessoa jurídica e comunicado manual.

Para envio automático diário em Linux, configure um cron parecido com:

```cron
0 8 * * * cd /caminho/do/projeto && /caminho/do/projeto/.venv/bin/python manage.py send_anniversary_emails >> logs/anniversary_emails.log 2>&1
```

No Windows, use o Agendador de Tarefas chamando:

```powershell
C:\Projetos\motormind_django_tailwind_daisyui\.venv\Scripts\python.exe manage.py send_anniversary_emails
```

O comando não reenvia aniversário/fundação para o mesmo cliente no mesmo ano quando já existe histórico com status **Enviado**.

## Estoque, peças e insumos

O módulo de estoque inclui:

- **Peças e insumos** em `/estoque/itens/`;
- **Movimentações** em `/estoque/movimentacoes/`;
- **Categorias globais de estoque** em `/configuracoes/estoque/categorias/`;
- **Marcas** em `/configuracoes/marcas/`.

Cada peça/insumo possui:

- tipo: peça ou insumo;
- SKU automático no padrão `PCA-000001` ou `INS-000001`;
- nome;
- descrição;
- categoria global de estoque;
- marca opcional;
- estoque mínimo;
- unidade de medida normalizada;
- preço de custo.

As unidades de medida são armazenadas na tabela `stock_unitofmeasure` e criadas pela migration inicial do app `stock`, incluindo `UN`, `PC`, `CX`, `L`, `ML`, `KG`, `G`, `M`, entre outras.

As listagens de peças/insumos, marcas e categorias globais de estoque são ordenadas alfabeticamente em ordem ascendente.

## Campos monetários

Todos os campos monetários devem usar o core `core.money`:

```python
from core.money import MoneyField, MoneyFormField, normalize_money, format_money_br
```

No banco, `MoneyField` usa `DecimalField(max_digits=12, decimal_places=2)` e normaliza os valores para duas casas decimais. Nos formulários, `MoneyFormField` aceita digitação no padrão brasileiro, como `1.234,56`, e converte para `Decimal`.

O filtro de template abaixo formata valores monetários no padrão brasileiro:

```django
{% load money %}
{{ objeto.valor|money_br }}
```

## Movimentações de estoque

A tabela `StockMovement` registra todas as movimentações de estoque. Os tipos disponíveis são:

- entrada;
- saída;
- ajuste positivo;
- ajuste negativo.

Cada movimentação grava:

- item movimentado;
- tipo;
- quantidade informada;
- quantidade assinada, positiva ou negativa;
- saldo após a movimentação;
- custo unitário;
- valor total;
- usuário que registrou;
- data/hora.

Movimentações não são editadas pela interface para preservar auditoria. Saídas e ajustes negativos são bloqueados quando deixariam o saldo abaixo de zero.

## Exclusão lógica

Clientes e fornecedores possuem:

```python
ativo = models.BooleanField(default=True)
excluido_em = models.DateTimeField(blank=True, null=True)
```

Ao excluir, o registro não é removido do banco. Ele é marcado como inativo e recebe `excluido_em`. As telas principais usam o manager padrão, que retorna apenas registros ativos.

Categorias e templates de mensagens usam `excluido_em` e, ao excluir, também são marcados internamente como inativos. A flag de ativo/inativo não aparece nos formulários de cadastro/edição.

## Modelo de usuário

O modelo `accounts.User` remove o campo `username` e usa:

```python
USERNAME_FIELD = "email"
REQUIRED_FIELDS = ["nome_razao_social"]
```

Clientes e fornecedores são modelos independentes em `core.models`, sem `ForeignKey` ou `OneToOneField` para `User`.

## Observação sobre CEP

A busca de CEP é feita no frontend por `static/js/cep.js`, usando HTTPS. Se o serviço externo estiver indisponível, o usuário ainda pode preencher o endereço manualmente.

## Ajuste de comportamento do menu

O layout principal usa `static/js/menu.js` para controlar os menus da navbar.

Comportamento implementado:

- ao abrir um menu principal, os demais menus principais são fechados;
- no menu mobile, ao abrir um submenu, os demais submenus irmãos são fechados;
- ao clicar fora da navbar, todos os menus são fechados;
- ao pressionar `Esc`, todos os menus são fechados;
- ao clicar em um link do menu, os menus abertos são fechados.

## Busca avançada com autocomplete

As listagens de clientes e fornecedores possuem busca avançada com autocomplete.

Em clientes:

```txt
/clientes/
/clientes/autocomplete/?q=termo
```

Em fornecedores:

```txt
/fornecedores/
/fornecedores/autocomplete/?q=termo
```

A busca geral consulta:

- nome ou razão social;
- email;
- WhatsApp;
- CPF/CNPJ, quando preenchido;
- CEP;
- logradouro;
- número;
- complemento;
- bairro;
- cidade;
- UF;
- categorias.

Também existem filtros avançados por:

- tipo de pessoa;
- categoria;
- aceite de marketing;
- cidade;
- UF.

A paginação preserva todos os filtros aplicados. As listagens de clientes e fornecedores são sempre ordenadas em ordem alfabética ascendente por nome/razão social.


## Alertas flutuantes

As mensagens do framework `django.contrib.messages` aparecem como alertas flutuantes no canto superior direito da tela e somem automaticamente.

Tempos configurados:

- sucesso e informação: 5 segundos;
- alerta: 9 segundos;
- erro: 15 segundos.

O usuário também pode fechar manualmente cada alerta pelo botão `X`.

## Busca avançada de peças e insumos

A tela `/estoque/itens/` permite combinar os filtros:

- busca geral com autocomplete por SKU, nome, descrição, marca, categoria ou unidade;
- tipo: peça ou insumo;
- categoria global de estoque;
- marca;
- unidade normalizada;
- situação do estoque: com estoque, zerado, sem estoque/negativo, abaixo do mínimo ou dentro/acima do mínimo;
- custo mínimo e custo máximo, usando máscara monetária com duas casas decimais.

O botão **Limpar** remove todos os filtros e retorna para a listagem completa. A listagem permanece sempre ordenada em ordem alfabética crescente por nome.


## Atualização v15 — fornecedor na entrada e busca avançada de movimentações

A movimentação de estoque agora possui o campo **Fornecedor**. Ele é obrigatório somente quando o tipo da movimentação for **Entrada**. Para **Saída**, **Ajuste positivo** e **Ajuste negativo**, o fornecedor não é exigido e não é gravado.

A tela `/estoque/movimentacoes/` recebeu busca avançada com autocomplete e filtros por:

- busca geral: SKU, item, fornecedor, usuário ou observação;
- tipo da movimentação;
- peça/insumo;
- fornecedor;
- usuário responsável;
- período inicial e final;
- quantidade mínima e máxima;
- custo unitário mínimo e máximo;
- valor total mínimo e máximo.

O botão **Limpar** remove todos os filtros aplicados. A paginação preserva os filtros durante a navegação entre páginas.

## Busca simples em categorias e funcionários

As telas de categorias e funcionários possuem busca simples com autocomplete:

```txt
/categorias/autocomplete/?q=termo
/funcionarios/autocomplete/?q=termo
```

## Operacional — serviços

A área **Operacional** possui o submenu **Serviços** em:

```txt
/operacional/servicos/
```

O cadastro de serviços possui:

- código automático no padrão `SRV-00001`;
- nome;
- descrição;
- duração em minutos;
- valor usando o core monetário do projeto, sempre com duas casas decimais;
- peças/insumos padrão associadas ao serviço;
- quantidade padrão por peça/insumo;
- exclusão lógica.

Endpoints principais:

```txt
/operacional/servicos/
/operacional/servicos/novo/
/operacional/servicos/autocomplete/?q=termo
/operacional/servicos/<id>/
/operacional/servicos/<id>/editar/
/operacional/servicos/<id>/excluir/
```

A busca de serviços consulta código, nome, descrição e peças padrão associadas. Também permite filtrar por duração mínima/máxima, valor mínimo/máximo e peça padrão.

## v18 - Modal reutilizável para seleção de peças padrão

- Criado componente modal reutilizável em `templates/includes/reusable_select_modal.html`.
- Criado JavaScript reutilizável em `static/js/reusable-select-modal.js`.
- Cadastro de serviços agora usa botão **Adicionar peça** no card de peças padrão.
- Ao clicar em **Adicionar peça**, abre uma modal com busca, dropdown de resultados, mini cards de peças/insumos, campo de quantidade e botões **Salvar** e **Cancelar**.
- Ao salvar, a peça aparece em uma lista read-only no serviço, mostrando SKU, nome, tipo, categoria, marca, quantidade padrão e custo unitário.
- A lista permite apenas exclusão da peça associada antes de salvar o serviço.
- O backend continua usando `ServiceDefaultPartFormSet`, preservando validações e salvamento do Django.
- Não há migrations novas nesta versão.

Arquivos principais alterados/criados:

```txt
templates/includes/reusable_select_modal.html
static/js/reusable-select-modal.js
static/js/service-parts.js
operations/templates/operations/service_form.html
operations/views.py
README.md
```

Para atualizar:

```bash
python manage.py check
npm install
npm run css:build
python manage.py runserver
```


## v19 - Quantidades inteiras

Todos os campos de quantidade do estoque e do operacional agora são inteiros:

- estoque mínimo de peças/insumos;
- quantidade da movimentação de estoque;
- quantidade assinada da movimentação;
- saldo após movimentação;
- quantidade padrão de peças/insumos associadas ao serviço.

A interface foi ajustada para aceitar apenas números inteiros nos campos de quantidade, incluindo a modal reutilizável de seleção de peças padrão. Os filtros de movimentação de estoque por quantidade também passaram a usar valores inteiros.

Novas migrations:

```txt
stock/migrations/0003_integer_quantities.py
operations/migrations/0002_integer_default_part_quantity.py
```

Para atualizar:

```bash
python manage.py migrate
python manage.py setup_roles
python manage.py check
npm install
npm run css:build
python manage.py runserver
```

## v20 - Combos de serviços

Implementado o cadastro de combos dentro do menu **Operacional**.

Incluído:

- submenu **Combos** em **Operacional**;
- código automático no padrão `CMB-00001`;
- nome;
- descrição;
- serviços associados;
- desconto percentual opcional;
- cálculo de subtotal dos serviços;
- cálculo do valor do desconto;
- cálculo do valor total do combo;
- exclusão lógica;
- busca avançada com autocomplete.

O cadastro de combo reutiliza o mesmo padrão do modal de peças padrão: botão **Adicionar serviço**, busca com dropdown, mini cards, botão **Salvar** e botão **Cancelar**. Após salvar na modal, o serviço aparece em uma lista read-only com apenas botão de exclusão.

Endpoints principais:

```txt
/operacional/combos/
/operacional/combos/novo/
/operacional/combos/autocomplete/?q=termo
/operacional/combos/<id>/
/operacional/combos/<id>/editar/
/operacional/combos/<id>/excluir/
```

A busca avançada de combos consulta:

- código do combo;
- nome;
- descrição;
- código dos serviços associados;
- nome dos serviços associados;
- descrição dos serviços associados.

Filtros disponíveis:

- desconto mínimo;
- desconto máximo;
- valor mínimo;
- valor máximo;
- serviço associado.

Nova migration:

```txt
operations/migrations/0003_servicecombo_servicecomboitem.py
```

Arquivos principais alterados/criados:

```txt
operations/models.py
operations/forms.py
operations/views.py
operations/urls.py
operations/admin.py
operations/migrations/0003_servicecombo_servicecomboitem.py
operations/templates/operations/service_combo_list.html
operations/templates/operations/service_combo_form.html
operations/templates/operations/service_combo_detail.html
templates/includes/reusable_select_modal.html
static/js/reusable-select-modal.js
static/js/combo-services.js
templates/base.html
accounts/management/commands/setup_roles.py
README.md
```

Para atualizar:

```bash
python manage.py migrate
python manage.py setup_roles
python manage.py check
npm install
npm run css:build
python manage.py runserver
```

## Versão v21 — Veículos no atendimento

Incluído o cadastro de **veículos** dentro do menu **Atendimento**.

Campos do cadastro:

- cliente proprietário;
- placa;
- tipo FIPE: carro, moto ou caminhão;
- marca;
- modelo;
- versão;
- quantidade de portas;
- combustível;
- KM;
- chassi;
- tipo de direção;
- ar condicionado;
- veículo modificado;
- observação.

A tela de cadastro possui uma seção de **Consulta FIPE** para buscar marca, modelo e ano/versão. A integração usa endpoints proxy internos do Django para consultar a FIPE e preencher os campos do veículo.

Endpoints criados:

```txt
/veiculos/
/veiculos/novo/
/veiculos/autocomplete/?q=termo
/veiculos/fipe/marcas/?tipo=cars
/veiculos/fipe/modelos/?tipo=cars&marca=59
/veiculos/fipe/anos/?tipo=cars&marca=59&modelo=5585
/veiculos/fipe/valor/?tipo=cars&marca=59&modelo=5585&ano=2014-3
/veiculos/<id>/
/veiculos/<id>/editar/
/veiculos/<id>/excluir/
```

Também foi adicionado:

- busca avançada com autocomplete para veículos;
- exclusão lógica para veículos;
- veículo listado na tela de detalhe do cliente;
- botão **Novo veículo** dentro do detalhe do cliente;
- permissões de veículos no comando `setup_roles`;
- menu **Atendimento > Veículos**.

Nova migration:

```txt
core/migrations/0006_vehicle.py
```

Para atualizar:

```bash
python manage.py migrate
python manage.py setup_roles
python manage.py check
npm install
npm run css:build
python manage.py runserver
```

## v22 - Sistema de OS

Esta versão adiciona o sistema de **Ordem de Serviço** dentro do menu **Operacional**.

### Menu

- Operacional
  - Ordens de Serviço
  - Serviços
  - Combos

### Ordem de Serviço

A OS possui:

- código automático no padrão `OS-00001`;
- cliente;
- veículo do cliente;
- status: aberta, diagnóstico, orçamento, aguardando aprovação, aprovada, em execução, aguardando peça, em teste, pronta, pronto para retirar, entregue, cancelada ou arquivada;
- data de abertura;
- previsão de entrega;
- data de finalização;
- KM atual;
- problema relatado;
- diagnóstico;
- observação;
- desconto percentual opcional;
- serviços associados;
- combos associados;
- peças/insumos avulsos;
- cálculo de subtotal de serviços, combos e peças;
- cálculo de desconto e total final;
- controle de baixa de estoque.

### Baixa de estoque da OS

A tela de detalhe da OS possui o botão **Baixar estoque** quando o usuário tem permissão para alterar OS e criar movimentação de estoque.

A baixa de estoque considera:

- peças/insumos avulsos da OS;
- peças padrão dos serviços adicionados;
- peças padrão dos serviços contidos nos combos adicionados.

A baixa cria movimentações do tipo **Saída** e marca a OS como `estoque_baixado=True`, impedindo baixa duplicada.

### Busca avançada

A tela de OS possui busca avançada com autocomplete por:

- código da OS;
- cliente;
- email do cliente;
- placa;
- marca/modelo do veículo;
- problema relatado;
- diagnóstico;
- serviços;
- combos;
- peças/insumos.

Também possui filtros por:

- status;
- cliente;
- veículo;
- período de abertura;
- valor mínimo;
- valor máximo.

### Atualização

Após substituir os arquivos, execute:

```bash
python manage.py migrate
python manage.py setup_roles
python manage.py check
npm install
npm run css:build
python manage.py runserver
```

No Windows PowerShell:

```powershell
python manage.py migrate
python manage.py setup_roles
python manage.py check
npm install
npm run css:build
python manage.py runserver
```

## Versão v23 - Configuração de prazo da OS e seleção automática de veículo

Incluído nesta versão:

- Nova tela em **Configurações > OS**:
  - `/configuracoes/os/`
- Configuração de **prazo padrão da OS em dias**.
- O campo **Previsão de entrega** da nova OS passa a vir preenchido automaticamente com:
  - data atual + prazo configurado;
  - hora atual do momento da criação.
- Exemplo: prazo configurado em 7 dias e OS criada em `03/06/2026 às 20h` gera previsão em `10/06/2026 às 20h`.
- Novo endpoint para veículos do cliente:
  - `/operacional/os/cliente-veiculos/?cliente=<id>`
- Ao selecionar um cliente no cadastro da OS, o sistema carrega os veículos daquele cliente e seleciona automaticamente o primeiro veículo encontrado.
- Ao editar uma OS, o veículo atual é preservado quando ele pertence ao cliente da OS.
- A lista de veículos do campo da OS fica restrita aos veículos do cliente selecionado.

Nova migration:

```txt
operations/migrations/0005_workordersettings.py
```

Arquivos principais alterados/criados:

```txt
operations/models.py
operations/forms.py
operations/views.py
operations/urls.py
operations/admin.py
operations/migrations/0005_workordersettings.py
operations/templates/operations/work_order_settings_form.html
operations/templates/operations/work_order_form.html
static/js/work-order-form.js
templates/base.html
accounts/management/commands/setup_roles.py
README.md
```

## v24 - Check-in de recepção do veículo

Esta versão adiciona o sistema de check-in de veículo vinculado à OS.

### Funcionalidades

- Novo submenu em **Atendimento > Check-ins**.
- Check-in vinculado à ordem de serviço.
- O cliente e o veículo são herdados automaticamente da OS selecionada.
- Registro de:
  - KM no check-in;
  - nível de combustível;
  - estepe;
  - macaco;
  - chave de roda;
  - documento do veículo;
  - objetos deixados no veículo;
  - avarias observadas;
  - observações gerais.
- Suporte a múltiplas fotos pelo celular/tablet usando `input type="file" accept="image/*" capture="environment"`.
- Geração de PDF do check-in.
- Envio do PDF por email para o cliente.
- Histórico no próprio check-in indicando se o PDF foi enviado, data do envio e erro técnico caso exista.
- Busca simples com autocomplete para check-ins.
- Exclusão lógica dos check-ins.

### Endpoints

```txt
/atendimento/checkins/
/atendimento/checkins/novo/
/atendimento/checkins/autocomplete/?q=termo
/atendimento/checkins/<id>/
/atendimento/checkins/<id>/editar/
/atendimento/checkins/<id>/excluir/
/atendimento/checkins/<id>/pdf/
/atendimento/checkins/<id>/enviar-email/
```

### Dependências novas

```txt
reportlab
Pillow
```

### Arquivos de mídia

As fotos enviadas no check-in são salvas em `MEDIA_ROOT`, por padrão:

```txt
media/checkins/AAAA/MM/
```

Em desenvolvimento, o projeto serve os arquivos de mídia quando `DEBUG=True`.

### Atualização

```bash
python manage.py migrate
python manage.py setup_roles
python manage.py check
npm install
npm run css:build
python manage.py runserver
```


## v26

- Corrigido `operations/templates/operations/vehicle_checkin_form.html` para deixar `{% extends 'base.html' %}` como primeira tag do template.
- Mantido `{% load static %}` logo depois do `extends`, corrigindo o erro `TemplateSyntaxError` na tela `/atendimento/checkins/novo/`.

## v29 - Área da mecânica e validação de estoque da OS

Alterações incluídas:

- Removido o card **Máquina de estados** da tela de detalhe da OS.
- Mantido o controle de alteração de status em um botão compacto **Alterar status** no topo da tela de detalhe da OS.
- Movido o **Histórico de estados** para o final da tela de detalhe da OS.
- Criada a área **Mecânica**, acessível apenas por usuário com função **Técnico** ou superusuário.
- Novo menu principal **Mecânica** com submenu **Fila de OS**.
- Nova fila da mecânica em `/mecanica/os/`.
- Detalhe operacional da OS para mecânica em `/mecanica/os/<id>/`.
- O mecânico pode acrescentar serviços, combos e peças/insumos avulsos na OS usando o mesmo padrão de modal reutilizável.
- O mecânico pode clicar em **Dar início ao serviço**.
- A OS só pode ir para **Em execução** se todas as peças previstas tiverem estoque suficiente.
- Quando a OS aprovada tem peça sem estoque suficiente, ela fica automaticamente como **Aguardando peça**.
- O bloqueio considera:
  - peças avulsas da OS;
  - peças padrão dos serviços;
  - peças padrão dos serviços dentro dos combos.
- OS com estoque já baixado não permite alteração de itens pela mecânica.

Novos endpoints:

```txt
/mecanica/os/
/mecanica/os/<id>/
/mecanica/os/<id>/iniciar/
```

Não há migrations novas nesta versão.

Comandos para atualizar:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
npm install
npm run css:build
python manage.py runserver
```

Validações executadas nesta versão:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python -m compileall -q accounts core communications config stock operations manage.py
npm install
npm run css:build
```

Também foi validado em shell Django:

- técnico acessa `/mecanica/os/` e `/mecanica/os/<id>/`;
- atendente recebe `403` na área da mecânica;
- OS aprovada sem estoque suficiente não inicia e muda para `Aguardando peça`;
- após entrada de estoque suficiente, a OS inicia e muda para `Em execução`.

## v31 - Travamento de dados estruturais da OS e peças de combos

Alterações incluídas:

- Após a OS ser aberta/salva, os seguintes campos ficam travados na edição:
  - cliente;
  - veículo;
  - KM atual;
  - previsão de entrega;
  - problema relatado.
- Esses campos continuam visíveis no formulário, mas não podem ser alterados depois da abertura da OS.
- O JavaScript de cliente/veículo respeita o travamento e não recarrega veículos quando a OS já existe.
- O combo, ao ser adicionado na OS, agora mostra também as peças padrão dos serviços vinculados ao combo.
- A tela de detalhe da OS mostra a origem das peças previstas para baixa de estoque, separando:
  - peça avulsa;
  - peça vinda de serviço;
  - peça vinda de serviço dentro de combo.
- A tela da mecânica também mostra a origem das peças previstas em um painel expansível.
- O detalhe do combo agora exibe as peças padrão de cada serviço associado.

Não há migrations novas nesta versão.

Comandos para atualizar:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
npm install
npm run css:build
python manage.py runserver
```

Validações executadas nesta versão:

```bash
python manage.py migrate --noinput
python manage.py setup_roles
python manage.py check
python manage.py makemigrations --check --dry-run
python -m compileall -q accounts core communications config stock operations manage.py
node --check static/js/reusable-select-modal.js
node --check static/js/work-order-items.js
node --check static/js/work-order-form.js
npm install
npm run css:build
```

Também foi validado via shell Django:

- peças padrão de serviço dentro de combo aparecem em `get_stock_requirement_sources()`;
- edição de OS existente preserva cliente, veículo, KM, previsão de entrega e problema relatado mesmo que um POST tente alterar esses campos.

## v33 - Bloqueio de OS cancelada e capacidade da oficina

- OS com status **Cancelada** não pode mais ser editada pela tela de edição, nem ter peças previstas ajustadas.
- O status **Cancelada** ainda pode ser movido para **Arquivada** pela ação de status, preservando o fluxo administrativo.
- Criada configuração de **capacidade da oficina** em `Configurações > OS`.
- A configuração permite informar quantas vagas físicas existem na oficina.
- A tela de configuração mostra vagas configuradas, ocupadas e disponíveis.
- A listagem de OS mostra um resumo da capacidade da oficina.
- O sistema bloqueia a abertura de uma nova OS quando todas as vagas estão ocupadas.
- Estados que ocupam vaga: Aberta, Diagnóstico, Orçamento, Aguardando aprovação, Aprovada, Em execução, Aguardando peça, Em teste, Pronta e Pronto para retirar.
- Estados que não ocupam vaga: Entregue, Cancelada e Arquivada.

Após atualizar, execute:

```bash
python manage.py migrate
python manage.py setup_roles
python manage.py check
npm install
npm run css:build
python manage.py runserver
```


## v34 - Peças padrão entram no valor da OS

- Corrigido o cálculo financeiro da OS para considerar todas as peças previstas.
- O subtotal de **Peças e insumos** agora soma:
  - peças avulsas adicionadas diretamente na OS;
  - peças padrão dos serviços adicionados na OS;
  - peças padrão dos serviços associados aos combos adicionados na OS.
- O cálculo usa a quantidade ajustada da OS quando houver ajuste manual.
- A tabela **Peças e insumos da OS** agora exibe:
  - quantidade padrão;
  - quantidade desta OS;
  - estoque atual;
  - valor unitário;
  - subtotal.
- A área **Origem das peças previstas** também mostra valor unitário e subtotal por origem.
- A tela da mecânica agora mostra valor unitário e subtotal das peças previstas.
- Exemplo corrigido: serviço de R$ 80,00 com filtro de óleo + 4 litros de óleo somando R$ 92,50 passa a mostrar R$ 92,50 no setor de peças da OS e R$ 172,50 no total, antes de descontos.

Não há migrations novas nesta versão.

Após atualizar, execute:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
npm install
npm run css:build
python manage.py runserver
```

## v35 - Pedido de compra no estoque

Incluído o sistema de pedido de compra no menu **Estoque**.

### Funcionalidades

- Novo submenu **Estoque > Pedidos de compra**.
- Pedido de compra manual com:
  - código automático `PC-00001`;
  - fornecedor opcional enquanto pendente;
  - status: pendente, solicitado, recebido e cancelado;
  - múltiplos itens;
  - quantidade inteira;
  - custo unitário usando o core monetário;
  - total calculado.
- Pedido de compra automático quando uma OS fica com falta de peça/insumo.
- Quando a OS é movida automaticamente para **Aguardando peça**, o sistema cria ou atualiza um pedido pendente vinculado à OS com os itens faltantes.
- Ao receber o pedido, o sistema cria movimentações de estoque do tipo **Entrada** para cada item.
- O recebimento exige fornecedor informado.
- Busca avançada com autocomplete para pedidos de compra.
- A tela de detalhe da OS mostra os pedidos de compra vinculados.

### Atualização

```bash
python manage.py migrate
python manage.py setup_roles
python manage.py check
npm install
npm run css:build
python manage.py runserver
```

Nova migration:

```txt
stock/migrations/0004_purchase_order.py
```


## v36 - Mensagens automáticas por status da OS

- Novo tipo de template: **Mudança de status da OS**.
- Nova automação no centro de mensagens: **Configurações > Mensagens > Mudança de status da OS**.
- É possível habilitar/desabilitar globalmente o envio por mudança de status da OS.
- É possível habilitar/desabilitar o envio individualmente para cada status da OS.
- Cada status pode usar um template próprio ou o template padrão de mudança de status.
- O envio é disparado automaticamente após uma transição válida de status da OS.
- O histórico de mensagens mostra código da OS e status que disparou o envio.

Variáveis disponíveis em templates de status da OS:

```django
{{ nome }}
{{ email }}
{{ ordem_servico.codigo }}
{{ os.codigo }}
{{ codigo_os }}
{{ status_anterior_label }}
{{ status_novo_label }}
{{ veiculo }}
{{ placa }}
{{ mensagem_status }}
{{ data_envio }}
```

## v37 - IA com instruções específicas por campo

Esta revisão adiciona instruções configuráveis por finalidade em **Configurações > IA** e também pelo Admin Django:

- Problema relatado: melhorar somente o relato do cliente, de forma curta e sem transformar em diagnóstico.
- Diagnóstico: detalhar melhor o serviço, desmontagem, esforço técnico, verificações e próximos passos sem inventar medições ou conclusões.
- Observação da OS: sugerir observações considerando os dados disponíveis da OS.
- Templates/mensagens: gerar ou melhorar email/WhatsApp considerando contexto, tipo do template e variáveis do sistema.

Nova migration:

```bash
python manage.py migrate ai_assistant
```

Validação recomendada:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python -m compileall -q accounts ai_assistant core communications config stock operations manage.py
node --check static/js/ai-assistant.js
npm run css:build
```
