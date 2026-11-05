# Captura e ambiente integrado — 2026-11-03

## Entregue

- Botão **Capturar vídeo** no Lumen e modo `workspace` que abre a mesa de captura.
- URL HTTPS do YouTube → legendas em português/inglês → resumo em português pelo Codex autenticado com ChatGPT → nota Lumen v1 → validação estrutural.
- Fonte preservada em `.local/capturas/<id>/conteudo/transcricao.txt`. Notas geradas ficam na mesma pasta, fora do vault.
- Conteúdo longo é dividido em partes, com síntese final; limite de 240 mil caracteres, sem truncamento silencioso. Cada chamada tem prazo de quatro minutos.
- Fila persistida, um executor, até cinco pendências e deduplicação por ID de vídeo. Capturas interrompidas são marcadas como falhas na reabertura. Não há repetição automática de chamadas de IA.
- Notas continuam `status: inbox`, `lumen_export: false`. Os fluxos anteriores de revisão/exportação para Atlas não foram substituídos.
- Ponte local em `127.0.0.1:43127`, apenas origens Atlas locais nas portas 5173 e 4180, sessão aleatória, JSON e limites de entrada. Não aceita URLs de páginas arbitrárias nem caminhos de arquivos.
- Atlas: captura em Notas/Hoje, acompanhamento da fila, acessos a Estudos, Foco, Notion e Spotify. Sem escrita automática de tarefas ou tempo estudado.
- Voz opcional no Atlas: português com quatro comandos e equivalentes em inglês. Depende do suporte do navegador e de permissão de microfone; serviços online do navegador podem processar áudio. Não mantém escuta permanente. Abertura externa exige clique para respeitar bloqueio de popups.

## Execução

Na raiz do Lumen: `.\.venv\Scripts\python.exe tools\lumen.py workspace`.

No Atlas, usar o mesmo endereço/porta em que seus dados já estão armazenados. A ponte aceita `http://127.0.0.1:4180`, `http://localhost:4180` e equivalentes em 5173. Cada origem tem armazenamento próprio; não migramos o banco pessoal.

## Custos e privacidade

Codex já foi encontrado autenticado por ChatGPT. A execução força esse método de login, remove variáveis de chave API do subprocesso e não faz fallback pago. Continua sujeita aos limites e disponibilidade do plano. Não compramos créditos nem instalamos modelos grandes.

Uma execução efêmera recebe apenas o material da captura; configuração pessoal, shell, agentes e pesquisa web são desativados. A transcrição é enviada ao serviço do Codex. A nota não comprova a precisão das legendas nem fatos atuais. A dependência de legendas é não oficial: vídeos privados, sem legendas, idiomas diferentes e bloqueios podem impedir a captura. Não se tenta contornar autenticação ou bloqueios.

## Notion conectado — publicação automática

O publicador do Lumen foi verificado usando a conexão Notion já autorizada no Codex. A mesa de captura publica automaticamente uma página na Biblioteca Lumen com Estado Revisar, sem copiar credenciais. Fonte e cópia Markdown permanecem locais; não há alteração do vault nem conclusão de tarefas. A etapa depende de Codex, conexão de internet, Notion conectado e limites disponíveis do plano ChatGPT.

O executor de resumo desativa aplicativos. O executor de publicação precisa das ferramentas conectadas: recebe somente a nota e instruções para criar uma página na biblioteca fixa, sem shell ou ações destrutivas. Não é um serviço com permissões isoladas por pasta no Notion; respeita as permissões concedidas ao Codex. Não alteramos permissões globais dos aplicativos.

A publicação pede criação e leitura de volta. Em caso de entrega incerta, o item preserva a nota local e não repete a criação automaticamente. Uma conexão futura indisponível não bloqueia a captura local.

O publicador por token nos campos avançados continua como alternativa opcional e não foi testado com credenciais reais. Tokens não são salvos em arquivos; essa modalidade usa parágrafos de texto e exige revisão explícita.

Biblioteca: <your Notion library URL>

Teste do publicador automático: https://app.notion.com/p/40d36cca869a81d9861cc72a7910380d

## Limites que permanecem

- Aceitação manual completa da transferência Lumen–Atlas anterior ainda pendente; os testes existentes foram preservados.
- Não migramos o acervo do Obsidian; isso exige inventário, backup e piloto de links/anexos.
- Hermes/Orca não foram instalados: o resumo foi implementado com o executor já disponível. Identidade do Orca continua ambígua.
- Não existe agendamento diário, captura da aba atual do Comet, controle completo do Cursor, playlist automática ou agente residente.
- Reconhecimento real de voz e uso cotidiano no Comet não foram verificados por microfone.

## Fontes de implementação

- https://github.com/jdepoix/youtube-transcript-api
- https://learn.chatgpt.com/docs/non-interactive-mode
- https://learn.chatgpt.com/docs/config-file/config-reference
- https://developers.notion.com/reference/post-page

## Verificação

Teste real com `Python in 100 Seconds`, do Fireship: captura de legendas, síntese em português e validação Lumen passaram. Publicação da mesma nota pela conexão Notion da conversa foi lida de volta. Nenhum arquivo do vault foi modificado.
# Atualização de interface e agentes — 03/11/2026

O iniciador agora abre uma janela Lumen com quatro áreas: Capturar, Biblioteca,
Arquivos e Contexto dos agentes. A leitura esconde os metadados técnicos por
padrão, preservando o Markdown original. A biblioteca abre no aplicativo Notion.
Preto e azul seguem a paleta compartilhada com Atlas.

A pasta `00 - Contexto dos agentes` no vault Repositorio recebe apenas registros
explícitos. Preparar/copiar contexto não transmite o conteúdo automaticamente.
A ponte local aceita ações fixas para abrir Lumen, Notion, Spotify, Obsidian e
Orca; não executa comandos arbitrários enviados pelo navegador.

Atalhos “Meu Ambiente” e “Agentes - Orca” foram criados no Desktop e no menu
Iniciar. Orca tem os dois projetos registrados. Hermes foi instalado, mas seu
login foi adiado pelo usuário; nenhuma inferência autenticada foi confirmada.
Feche versões antigas do Lumen antes de abrir a nova para liberar a porta local.


## Atualização operacional
A interface React deixou de usar mocks: o serviço runtime.py expõe a API local autenticada e serve o Atlas compilado no endereço anterior. KnowledgeInbox persiste fontes, notas e recibos por destino. Resumos usam Codex/ChatGPT; exportação exige confirmação. Existe deduplicação por fonte/destino/preferências e proteção contra sobrescrita e repetição de entrega incerta. Atalhos Lumen, Atlas e Meu Ambiente iniciam o serviço sem terminal de desenvolvimento. O executor completo passou com 186 testes. O login Hermes permanece pessoal, pelo atalho Conectar Hermes.
