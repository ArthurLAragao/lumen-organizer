# Stage 9D — interfaces de transferência manual

Escopo: exportação no Lumen e importação/recuperação no Atlas. Dados usados
na implementação e nos testes são fictícios. Stage 9E (aceitação manual do
fluxo completo) permanece pendente. Nenhuma pesquisa real foi autorizada.

## Separação e confirmação

O botão **Exportar para Atlas** abre uma janela independente. Selecionar o
vault nessa janela não troca a configuração da importação para o Obsidian.
A sequência é: selecionar vault/nota/categoria, validar, registrar identidade
explicitamente se nova, preparar a versão, escolher o arquivo de saída,
revisar e confirmar. Faculdade e projetos exigem subpasta existente explícita.

A interface delega elegibilidade, localização, identidade, hashes e preparação
a `AtlasExporter`, `ExportRegistry` e `DestinationPolicy`. O adapter de
apresentação controla apenas seleção, jobs, confirmação e cópia segura do
pacote retido. O worker e o núcleo de importação permanecem inalterados.

Não há botão que declare revisão humana. `status`, `lumen_export`, IDs e
conteúdo não são alterados. Nota elegível exige `status: reviewed`,
`lumen_export: true` booleano e estrutura/localização válidas. Os diagnósticos
editoriais permanecem visíveis. A prévia inclui o YAML completo, inerte,
selecionável, copiável e com rolagem. Caminhos completos estão disponíveis em
campos somente leitura e na confirmação.

Alterar seleção, baseline ou destino invalida a confirmação. O núcleo verifica
novamente a origem na gravação. Cancelar antes da confirmação não gera pacote.
O destino deve ser um diretório existente, fora do vault e do registro local.
A publicação usa os guards de diretório e rename sem sobrescrita do projeto.

## Identidade, baseline e recuperação

O registro continua separado do histórico antigo de importações, sob
`.local/atlas-export/`. Abrir a janela não cria um registro novo. A criação
exige confirmação específica, com aviso sobre registros perdidos. Uma nota
movida ou registro perdido exige recuperação/vinculação explícita pelos APIs
existentes; a interface não adota notas por similaridade.

A lista de baselines apresenta somente exportações preparadas da identidade
atual. Nenhuma é selecionada automaticamente. Escolher uma referência anterior
não comprova entrega nem substitui a decisão de conflito do Atlas.

Primeiro o núcleo retém o pacote verificado no registro. Depois a interface
copia exatamente esses bytes para o arquivo escolhido. Se a cópia falhar, o
arquivo retido permite **Salvar pacote já preparado** sem gerar nova
exportação. Colisões nunca sobrescrevem. Se publicação ou histórico ficar
incerto, uma nova tentativa fica bloqueada e o diagnóstico pede conferência.
**Conferir registro** usa a reconciliação existente; não repete gravações nem
apaga arquivos. Recuperação de staging incompleto continua sendo técnica pelos
APIs existentes; a janela não oferece reconstrução silenciosa.

O resultado de sucesso é:

> Pacote preparado. A importação no Atlas ainda não foi confirmada.

`delivery` permanece `unknown`, inclusive após uma cópia bem-sucedida. Não há
protocolo de recibo, sincronização ou atualização automática de baseline.

## Abrir exclusivamente com dados fictícios

Exemplo de raiz pública fictícia: `C:\Projetos\Lumen`.

```powershell
Set-Location 'C:\Projetos\Lumen'
.\.venv\Scripts\python.exe -B tools\stage9d_demo.py
```

O script cria uma área única em `.local/demos/<id>/`, imprime os caminhos do
vault, da nota autorizada fictícia e da pasta de pacotes, e inicia o aplicativo
sem carregar a configuração pessoal. Na janela de exportação, selecione esses
caminhos impressos; categoria `ferramentas`. Crie o registro apenas nessa demo,
registre a nova identidade e confirme a exportação para `Pacotes-Ficticios`.

Para abrir a versão normal: `.\.venv\Scripts\python.exe tools\lumen.py gui`.
Não use configuração/nota pessoal para a aceitação desta etapa.

No Atlas, em outro terminal, usando uma raiz fictícia `C:\Projetos\Atlas`:

```powershell
Set-Location 'C:\Projetos\Atlas'
$env:VITE_LUMEN_TEST_SESSION = 'stage9d-revisao-01'
npm run dev -- --config vite.lumen-test.config.ts
```

Abra **http://127.0.0.1:4189/notas** em um perfil temporário separado ou janela
InPrivate nova. A configuração exige sessão explícita e não procura `.env` na
raiz. A interface Lumen mostra o identificador e o banco
`atlas-lumen-test-stage9d-revisao-01`. Uma nova sessão seleciona um banco novo;
não apaga nem substitui bancos anteriores. Não use a origem de produção.

Em Notas, **Importar do Lumen** é separado de Markdown e backup completo.
Selecione o pacote fictício, confira plano/diferenças/avisos, revise e confirme.
**Histórico Lumen** permite selecionar uma atualização, consultar a versão
anterior, revisar o efeito e confirmar uma restauração protegida.

O histórico do Atlas é local ao navegador, excluído dos backups atuais, com
limite de 100 operações/20 MiB e sem limpeza automática. Sua perda pode bloquear
atualizações por falta de evidência. Criações não são revertidas por exclusão.
Drafts em memória e no armazenamento real de rascunhos são somente consultados;
falha de leitura bloqueia. Não há atomicidade entre localStorage e IndexedDB.

## Arquivos desta etapa

Novos: `src/lumen_organizer/export_workflow.py`, `export_ui.py`,
`tests/test_export_workflow.py`, `tools/stage9d_demo.py` e este documento.
Alterados: `src/lumen_organizer/ui.py` (acesso à janela e fechamento seguro),
`README.md` e `docs/gui-workflow.md` (acesso à documentação).

## Testes e revisão

```powershell
.\.venv\Scripts\python.exe -B tools\run_tests.py
```

Baseline executado: **144 testes**, sem falhas/erros/skips (36,492 s).
Regressão intermediária: **156 testes**, sem falhas/erros/skips (22,877 s).
Suite nova final isolada: **14 testes**, sem falhas/erros/skips (5,443 s).
Regressão final: **158 testes**, sem falhas/erros/skips (**30,836 s**).
No Atlas, a regressão completa passou com **1.042 testes / 81 arquivos**
(333,97 s); typecheck, lint e build também passaram. As duas jornadas no Edge
isolado passaram, inclusive a conferência de geometria da confirmação mobile.

São testes automatizados de workflow/IO e widgets Tk reais, com pickers e
confirmações nativas controlados pelos testes, diretórios temporários e auditoria
de escritas. Incluem elegibilidade, cancelamento, origem/destino alterados,
colisão, cópia retida, registro incompleto, reconciliação e entrega desconhecida.
Geometria/foco foram verificados com escalas **Tk** de 100%, 125%, 150% e 200%.
Isso não equivale a testes de DPI do Windows, monitor físico, leitor de tela ou
aceitação visual/manual. Não se afirma acessibilidade completa.

Revisão manual pendente (Stage 9E):

- Confirmar o ambiente fictício e os caminhos antes de selecionar a nota.
- Conferir YAML, título, identidade, avisos e arquivo completo de saída.
- Cancelar uma revisão e verificar que não surgiu pacote.
- Confirmar um pacote e conferir que o resultado não declara entrega.
- No Atlas isolado, confirmar criação e reimportação idêntica sem timestamp novo.
- Conferir uma atualização fictícia e a restauração protegida de sua versão anterior.
- Conferir teclado, rolagem, caminhos longos e escala real do Windows.

Nenhum acesso a notas/configurações pessoais, vault real ou bancos pessoais do
navegador é necessário ou autorizado por estes comandos de teste. Não houve
alteração de skill, dependências, schema, backup, tarefas, metas, foco ou XP.

## Encerramento — 2026-10-18

No Atlas, após o último ajuste de posição das ações, passaram novamente os
**23 testes / 4 arquivos** Stage 9D (18,83 s), **2 jornadas Edge isoladas**
(35,3 s), lint e build com typecheck. A regressão completa de 1.042 testes
precedeu somente esse ajuste final de posição, coberto pelos checks focados.
As capturas foram inspecionadas; não equivalem a aceitação manual Stage 9E.

Git do Lumen: master sem commits, **60 arquivos untracked** (55 no baseline),
nada staged. Git do Atlas: main em 5a113da inalterado, mudanças anteriores
preservadas e alterações desta etapa sem staging. git diff --check passou nos
dois projetos; como o Lumen ainda é untracked, esse comando não é uma revisão
de whitespace de seus novos arquivos. Nenhum commit/push/publicação.

Não se consultaram notas/configurações pessoais ou conteúdo do vault real para
esta verificação. Não se acessaram bancos pessoais do navegador. A confirmação
se refere às operações desta etapa, sem alegar uma comparação global de arquivos
do vault ou das bases pessoais. Stage 9D para aqui, aguardando revisão.
