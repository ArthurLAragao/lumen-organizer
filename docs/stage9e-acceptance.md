# Stage 9E — aceitação manual Lumen → pacote → Atlas

Data da preparação: **2026-10-18**. Estado: **PAUSADO por solicitação do usuário
para auditoria UX/UI; nenhum cenário manual aprovado ainda**. Este documento será atualizado após os relatos do usuário e
as verificações técnicas autorizadas. Não equivale ao relatório automatizado 9D.

## Ambiente e limites

- Lumen: `master`, HEAD `f31d355`, limpo antes da preparação.
- Atlas: `main`, HEAD `5a113da`, alterações 9C/9D anteriores preservadas; nada
  staged. Nenhum arquivo do aplicativo Atlas foi alterado nesta preparação.
- Aplicativo Lumen aberto pelo helper existente `tools/stage9d_demo.py`, sem
  carregar settings pessoais. A janela mantém o título da versão demo 9D;
  ela é a versão sob aceitação manual 9E.
- Área local única: `.local/demos/ebb666e8a0104501b033d485c264acd4/`.
- Vault exclusivamente fictício: `Vault-Ficticio/` nessa área. Categoria:
  `Ferramentas e Workflow (ferramentas)`.
- Atlas: origem **http://127.0.0.1:4189**, sessão
  **stage9e-20261018-c264acd4**, banco
  **atlas-lumen-test-stage9e-20261018-c264acd4**.
- Edge visível com perfil novo e separado `Perfil-Atlas-9E/` na área local;
  não reutiliza perfil pessoal. Requisições externas bloqueadas pelo ambiente
  de teste. Não foi aberto armazenamento pessoal do navegador.
- Uma conexão local de depuração do navegador de teste foi reservada para
  futuras leituras de evidência, limitadas a essa origem/banco após os relatos
  do usuário. Não houve consulta de dados do navegador pelo helper na abertura.
- Nenhum clique de exportar/importar/restaurar foi automatizado. A inicialização
  normal do aplicativo pode criar seus exemplos no banco novo; isso não é
  evidência de importação nem aprovação de um cenário.
- Sem mudanças de funcionalidades, redesign, dependências, skill, vault real,
  tarefas, metas, foco ou XP. Sem commit, push ou deploy nesta etapa.

Comandos usados (a raiz pública abaixo é apenas exemplo):

```powershell
Set-Location 'C:\Projetos\Lumen'
.\.venv\Scripts\python.exe -B -u tools\stage9d_demo.py

# Em outro terminal:
Set-Location 'C:\Projetos\Atlas'
$env:VITE_LUMEN_TEST_SESSION = 'stage9e-20261018-c264acd4'
npm run dev -- --config vite.lumen-test.config.ts
```

O helper Lumen cria uma área nova em cada execução. Para esta aceitação,
continuar nas janelas já abertas e na área identificada acima. Se uma janela
for fechada ou o servidor parar, registrar antes de reiniciar; não trocar de
perfil, sessão ou registro silenciosamente.

## Inventário e tabela de execução

Definições relativas à área local única:

- **N**: `Vault-Ficticio/01 - Conhecimento/Ferramentas e Workflow/`.
- **V**: `Versoes-Ficticias/` (snapshots; não selecionar diretamente na exportação).
- **P**: `Pacotes-Ficticios/` (ainda vazio na conferência da preparação).

Fixture existente reutilizada: `tests/fixtures/atlas-export/reviewed.md`.
A nota ativa `N/nota-ficticia-autorizada.md` e `V/fluxo-v1.md` preservam seus
852 bytes. Título: **Fictional Atlas transfer**; tags `fictional`, `teste`;
`created: "2026-10-10"`, `source: fictional-test`, `status: reviewed`,
`lumen_export: true`, `atlas_action: none`, IDs do Markdown vazios.
São metadados do exemplo existente; não representam revisão humana ou pesquisa
real nesta execução. A seção Fontes declara que não há fontes externas.
O wikilink inexistente é deliberadamente fictício e não deve ser resolvido.

Os snapshots v2/v3 preservam título, origem, data e lifecycle. Acrescentam uma
tag de versão e uma seção técnica identificável, antes do Registro pessoal,
sem preencher o registro. Somente quando chegar o respectivo cenário será
substituída a cópia ativa no vault fictício, após conferir seu hash anterior;
os snapshots de todas as versões ficam preservados. Isso mantém o mesmo caminho
e a identidade registrada, sem adoção por similaridade.

| Ordem | Cenário | Arquivo selecionado / preparação | Resultado esperado |
|---|---|---|---|
| 1 | Exportação e criação | Lumen: `N/nota-ficticia-autorizada.md`; Atlas: `P/01-criacao.lumen-atlas.json`, a ser gerado pelo usuário | Elegível; pacote preparado com entrega desconhecida; plano Criar nota; uma nota com conteúdo/YAML/tags corretos |
| 2 | Reimportação idêntica | Exatamente `P/01-criacao.lumen-atlas.json` | Reimportação idêntica; nenhuma cópia, alteração de timestamp ou entrada adicional no histórico |
| 3 | Atualização elegível | Copiar `V/fluxo-v2.md` para a mesma nota ativa; exportar `P/03-atualizacao.lumen-atlas.json` com o baseline explicitamente selecionado da criação conferida | Diferenças visíveis; mesma identidade, título, criação e relações; conteúdo/tags atualizados |
| 4 | Conflito | Edição local identificável salva no Atlas; ativar `V/fluxo-v3.md`; exportar `P/04-conflito.lumen-atlas.json` com referência v2 | Bloqueio por conflito; edição local intacta; sem merge/força |
| 5 | Draft | Mesmo pacote `P/04-conflito.lumen-atlas.json`; edição pendente pelo editor real | Draft detectado e atualização bloqueada; não apagar/salvar draft por automação |
| 6A | Recuperação permitida | Nota separada `N/recuperacao-ficticia-9e.md`, snapshots `V/recuperacao-v1.md` e `V/recuperacao-v2.md`; pacotes `P/06-recuperacao-v1.lumen-atlas.json` e `P/06-recuperacao-v2.lumen-atlas.json` | Preparar criação/atualização manualmente, escolher a operação de atualização no Histórico Lumen e restaurar sua versão anterior; somente essa nota muda |
| 6B | Recuperação bloqueada | Reaplicar manualmente o pacote de recuperação v2 após a restauração; salvar uma edição local posterior e selecionar a nova operação no histórico | Bloqueio por edição posterior; nenhum retorno forçado; não confundir com operação já restaurada |
| 7A | Cancelar exportação | `N/cancelamento-ficticio-9e.md`; destino planejado `P/07a-cancelado.lumen-atlas.json` | Cancelar na revisão; arquivo planejado e nova exportação preparados não devem existir; identidade previamente registrada pode permanecer |
| 7B | Cancelar importação | Exportação confirmada separadamente para `P/07b-apenas-pacote.lumen-atlas.json`; cancelar a criação no Atlas antes da confirmação de escrita | Pacote legitimamente gerado permanece; nenhuma nota/entrada de histórico correspondente no Atlas |

Para isolar o bloqueio de draft no cenário 5, orientar primeiro a remoção manual
somente do marcador de conflito da nota fictícia e seu salvamento pelo usuário,
depois criar um marcador de draft sem salvar. Não executar essa preparação
automaticamente. Se o usuário mantiver o conflito, registrar os dois bloqueios
e a limitação de isolamento. O draft será preservado enquanto a recuperação
usa outra nota fictícia.

Os pacotes são **futuros**, não fixtures pré-exportadas pelo agente. As
identidades serão registradas e as exportações/importações/restaurações
confirmadas pelo usuário nas interfaces. Um pacote salvo não comprova entrega.
Os baselines exigem escolha explícita, após confirmação visual e técnica da
versão efetivamente presente no Atlas fictício.

## Verificações técnicas da preparação

Executado: validação estrutural/perfil de exportação dos seis snapshots com
os componentes existentes; validação completa de localização autorizada das
três notas ativas no vault fictício. **Zero erros bloqueantes e zero avisos
editoriais** em todas as entradas. Não foi criado validador novo.

| Snapshot | Bytes | SHA-256 |
|---|---:|---|
| fluxo-v1.md | 852 | f57f8ac5e245538b6701c364d4be0de714dc23b5e13849f6dca9ad495efb904c |
| fluxo-v2.md | 981 | 738e051eb783ecf2b005b51dfd5a55b66649bc517c9fe23a8eff37d66bbd1853 |
| fluxo-v3.md | 981 | 7d276ff664fbc08a70cfbd74dd2e90fa67b1b6d62825843157cf20cbc9d39afb |
| recuperacao-v1.md | 867 | b97ecd88b0c7ee6cc77b5af6d83dcbcaafd6e97fcb0e97650a4bfe62e8f923e5 |
| recuperacao-v2.md | 996 | 084e2661a481197739011222d410cf75bb8795669d0eb250ca9e7371507196e9 |
| cancelamento-v1.md | 866 | 91681c0b7791dc564bf2f0e4d5ee4752993c7a55df363482cde4f2e1ffdc2a37 |

O Atlas acrescenta os avisos de wikilinks preservados sem resolução e histórico
local fora dos backups. Eles são esperados e não devem ser ocultados. A
conferência pré-teste encontrou zero pacotes e nenhum registro de exportação;
o agente não registrou identidades nem chamou commit/execute/restore.

## Evidência por cenário

| Cenário | Confirmação visual do usuário | Verificação técnica após confirmação | Situação |
|---|---|---|---|
| 1 | Captura: rejeição esperada no perfil de entrada Obsidian | Exportação/importação ainda não confirmadas; sem leitura posterior de artefatos ou banco | Em andamento; aceitação pendente |
| 2 | Aguardando | Aguardando | Não executado |
| 3 | Aguardando | Aguardando | Não executado |
| 4 | Aguardando | Aguardando | Não executado |
| 5 | Aguardando | Aguardando | Não executado |
| 6A/6B | Aguardando | Aguardando | Não executado |
| 7A/7B | Aguardando | Aguardando | Não executado |

Após cada relato, ler somente os arquivos dessa área local e o banco/perfil
fictícios identificados. Comparar bytes/hashes do Markdown com o pacote, estado
`prepared`/`delivery: unknown` no registro local, conteúdo/ID/timestamps/links da
nota e entradas do histórico Lumen no Atlas. Guardar snapshots de evidência
somente em `.local/`. Comparar também as outras entidades/metadata do banco de
teste quando a afirmação de ausência de efeitos exigir um antes/depois.

Não concluir preservação de hashes, timestamps ou outras entidades a partir de
mensagem de sucesso ou relato visual. Separar observação visual, leitura técnica
executada, resultado automatizado anterior e cenário pendente. Nunca repetir
uma operação de escrita para investigar um resultado incerto.

### Observação durante o cenário 1

A captura enviada pelo usuário mostra a nota fictícia autorizada na tela de
importação para Obsidian. Esse perfil exige `status: inbox` e
`lumen_export: false`, portanto rejeitou corretamente os valores de exportação
`reviewed` e `true`. A captura não demonstra falha do perfil de exportação.
Orientação: abrir **Exportar para Atlas** e selecionar a mesma nota nessa janela,
sem alterar suas propriedades. Nenhuma correção de nota ou código foi aplicada.
O resultado da validação de exportação ainda aguarda relato do usuário.

Em 2026-10-18, o usuário enviou uma segunda captura, agora da janela
**Exportar para Atlas**, mostrando o painel esquerdo colapsado: os controles
de origem e preparação não ficam legíveis. O agente também observou esse
defeito na janela fictícia em execução. Aceitação 9E pausada para auditoria
e proposta de correção, sem concluir ou reiniciar cenários. A captura não
confirma exportação ou importação. Fixtures, pacotes, identidades, histórico
e evidências anteriores devem ser preservados; nenhuma operação de escrita
do fluxo 9E será repetida para limpar o estado.

## Resultados automatizados anteriores e limitações

O relatório 9D registra 158 testes Python, 1.042 testes Atlas e duas jornadas
automatizadas Edge aprovados; os checks focados finais também passaram.
Essas evidências são anteriores e **não foram reexecutadas nesta preparação**;
não aprovam a aceitação manual 9E. A validação das fixtures acima foi executada
agora, sem exportar/importar.

Não se promete atomicidade localStorage/IndexedDB. Histórico de recuperação
local: 100 operações/20 MiB, não incluído nos backups atuais, sem limpeza
automática. A operação de criação não é revertida por exclusão. Controle de
versão obsoleta, conflitos e drafts permanece como implementado.

## Arquivos e Git desta preparação

- Novo documento: `docs/stage9e-acceptance.md`.
- Artefatos locais ignorados: demo criado pelo helper existente, seis snapshots
  Markdown e três notas ativas fictícias (uma já criada pelo helper), manifesto
  `stage9e-session.json`, estado local da demo e perfil isolado do Edge.
- Não foram alterados fixtures originais, código do aplicativo, skill ou vault
  pessoal. O servidor pode gerar seus caches normais, ignorados pelo Git.
- Esperado no Lumen após preparar: somente este documento untracked, HEAD
  inalterado. No Atlas, alterações 9D anteriores preservadas; nenhum arquivo
  tracked modificado por esta preparação. Sem staging/commit/push/deploy.

**Stage 9E continua pendente até os resultados de todos os cenários previstos.**
