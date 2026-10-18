# Incoming Lumen v1 contract

This implements the installed lumen-research format plus the approved amendment:
`atlas_action` accepts both `none` and `suggest`. It does not modify the skill.

## Structural rules

- A regular `.md` file, at most 2 MiB (2,097,152 bytes).
- UTF-8, with optional UTF-8 BOM. NUL bytes are rejected.
- Frontmatter begins at the first line with standalone `---` and ends at another
  standalone `---`. Original BOM, comments, line endings, and whitespace survive.
- YAML content between separators is at most 64 KiB (65,536 UTF-8 bytes).
- One mapping with string keys; no duplicate keys, explicit tags, anchors,
  aliases, directives, merge keys, or nested containers. Lists of strings are
  supported. A scanner budget of 4,096 tokens and maximum depth of eight bounds
  parser work before SafeLoader constructs values.
- The Markdown body must contain non-whitespace text.

## Required properties

| Property | Accepted value |
|---|---|
| `lumen_schema` | Integer `1`, excluding boolean/string lookalikes |
| `title` | Nonempty string |
| `type` | String `research` |
| `topic` | `[a-z0-9]+(?:-[a-z0-9]+)*` |
| `tags` | List of strings; an empty list is structurally valid |
| `source` | Nonempty string, including other truthful origin identifiers |
| `created` | Real calendar date in `YYYY-MM-DD`, quoted or unquoted |
| `status` | String `inbox` |
| `lumen_export` | YAML boolean false; the quoted string `"false"` is invalid |
| `atlas_action` | String `none` or `suggest` |
| `atlas_task_id` | Empty string |
| `atlas_goal_id` | Empty string |

PyYAML's safe boolean spellings are accepted according to their parsed type;
canonical lowercase `false` is recommended. Date scalars remain strings during
parsing and are checked with the calendar validator. Unsupported schemas and
lifecycle fields produce errors; the importer does not repair them.

## Advisory warnings

- First level-one heading absent or inconsistent with `title`.
- Missing recommended sections: `Resumo`, `Explicação`, `Exemplos e aplicação`,
  `Revisão`, `Fontes`, or `Registro pessoal`.
- Unknown simple YAML properties. They survive the byte copy but cannot influence
  a destination, command, review state, or export action.

`Pontos de atenção` is optional. Heading checks skip fenced code examples.
Warnings do not imply the research is inaccurate or authorize corrections.
Question quality, source truthfulness, actual creation provenance, and personal
review are not verified automatically. No URLs are fetched.

Diagnostics use stable codes and messages, optionally identifying a known field
or line. Parser exceptions are never copied into persistent logs. Validation
results contain no note when a structural error occurs.

## Import semantics

Import copies the approved bytes. It adds no category/property/ID to the note,
does not change `created` or `source`, does not mark `reviewed`, and does not
enable export. Review, import, and export authorization remain separate actions.

## Authorized destinations

All paths are relative to a locally configured vault, never a personal default.

| Category | Existing destination |
|---|---|
| `aws-cloud` | `01 - Conhecimento/AWS e Cloud` |
| `linux-devops` | `01 - Conhecimento/Linux e DevOps` |
| `programacao` | `01 - Conhecimento/Programação` |
| `ia` | `01 - Conhecimento/Inteligência Artificial` |
| `seguranca` | `01 - Conhecimento/Segurança` |
| `ferramentas` | `01 - Conhecimento/Ferramentas e Workflow` |
| `indefinido` | `00 - Inbox/Pesquisas` |
| `faculdade` | Explicit existing descendant of `02 - Faculdade` |
| `projetos` | Explicit existing descendant of `03 - Projetos` |

No category is inferred. Fixed destinations accept no additional subfolder.
Traversal, device/UNC paths, alternate data streams, and reparse-point ancestors
are rejected. Filenames are individual Windows-compatible `.md` basenames,
at most 180 characters, excluding device names and trailing dots/spaces.
