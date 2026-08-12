# micro1 — Prep entrevista AI (Mainframe Developer / Software Engineer COBOL)

**Candidato:** Edenilson Teixeira Paschoa  
**E-mail:** edenilson.adm@gmail.com  
**Application ID:** `6ebc2fa3-ebee-4380-823c-fd62d0c7a3e7`  
**Interview link:** https://www.interview.micro1.ai/intro/micro1/?candidate=37cb9220-550d-4072-b837-471a943fa44d&ping=ok  
**Prazo:** 29 Jul 2026 23:40  
**Formato:** AI Interview + Coding Exercise (~53 min)  
**Foco:** COBOL Programming & Legacy Code Analysis, Data Management, Debugging & Maintenance, Testing & QA, Code Review & Technical Reasoning

---

## 1. Elevator pitch (60–90s, EN)

> I’m Edenilson Teixeira Paschoa, a Brazilian software professional with 15+ years in enterprise IT. I spent about six years at Itaú Unibanco working hands-on with mainframe and COBOL — banking risk batch systems, JCL, DB2, Easytrieve Plus, SAS, night on-call for the batch mesh, production support and evolutionary changes. Later I led RPA architecture (Automation Anywhere, UiPath, Blue Prism) for large banks and telcos, then software engineering at Mercado Livre and B3, and I’m currently an Operations Analyst / SRE at B3 working on AIOps, CI/CD, observability and production LLM operations.  
> I’m strong at decoding complex legacy code, documenting business rules clearly, spotting edge cases, and working remotely with clear written communication — which maps directly to annotating COBOL for high-quality AI training data.

## 2. Availability / logistics (corrigir o formulário que mandou 1h/semana)

| Pergunta | Resposta recomendada |
|---|---|
| How soon can you start? | **Immediate to 7–14 days** (can prioritize evenings/weekends sooner) |
| Hours per week | **30–40 hours/week** (contract/remote, flexible) |
| Timezone | America/Sao_Paulo (BRT/BRST) |
| English | Professional working proficiency — strong reading/writing for technical docs; comfortable spoken for remote collab |
| Location | Jundiaí – SP, Brazil / Latin America remote |
| Sponsorship | Brazilian citizen — no US visa sponsorship needed for remote LATAM contract |

## 3. COBOL experience (deep dive)

### Where / when
- **Itaú Unibanco Holding** — Nov/2009–Apr/2015  
  - Banking **risk systems** (risco bancário)  
  - **Batch mesh** maintenance, night on-call  
  - Transfer/treatment of sequential mainframe bases for business users (SAS + SQL)  
  - Small evolutionary projects (up to ~400h) in “Caixa Rápido” team  
  - Support tools including mainframe debug (**EXPEDITER**)  
  - Excel/Access/SharePoint reporting bases; indicators/statistics  

### Stack
- **COBOL**, **JCL**, **DB2**, **Easytrieve Plus**  
- **SAS** (~1 year focused)  
- Mainframe batch operations, file processing, production support  
- Documentation for ops/users; SQL for robots later in career  

### How this maps to micro1 scope
| micro1 asks | You demonstrate |
|---|---|
| Analyze existing COBOL codebases | Years reading/maintaining banking COBOL |
| Document logic, workflows, business rules | Production docs + RPA architecture docs |
| Edge cases / ambiguities | Night batch failures, risk domain edge cases |
| Test cases / real-world scenarios | Batch validation, postmortems, QA mindset from SRE |
| Remote autonomous delivery | RPA delivery + current remote-friendly ops work |

## 4. Sample Q&A (EN)

### Tell me about yourself
Use elevator pitch above.

### Why this role / why micro1?
> I want to put deep COBOL/mainframe experience to work on frontier AI data quality. Documenting legacy logic accurately and catching edge cases is something I’ve done for years in banking production — not theory. micro1’s model (expert contribution, remote contract) fits how I already work.

### Describe a complex COBOL/mainframe system you worked on
> At Itaú, banking risk batch systems processed large sequential files overnight. I supported the mesh, fixed failures under time pressure, used EXPEDITER for debugging, and prepared bases for business areas with SAS/SQL. Failures were high-impact: delayed risk metrics, regulatory pressure. I learned to isolate root cause fast, document the rule, and harden the next run.

### How do you document legacy code for someone who never saw it?
1. Purpose of program (business outcome)  
2. Inputs/outputs (files, DB2 tables, copybooks)  
3. Control flow (paragraphs / PERFORM structure)  
4. Key business rules and conditions (IF/EVALUATE)  
5. Error handling and restart points  
6. Edge cases (empty file, partial run, reprocess, calendar effects)  
7. Short worked example with sample data  

### Edge case example
> Month-end risk batch with partial file from upstream. Job abended mid-mesh. Restart without reprocessing committed steps required careful checkpoint analysis and JCL restart parameters — classic mainframe operational edge case AI datasets need annotated.

### Testing approach for COBOL programs
- Unit-like: paragraph-level with controlled copybook data  
- File comparison (expected vs actual sequential outputs)  
- Boundary: empty, single-record, max volume, invalid codes  
- Regression after copybook/layout change  
- Parallel run (old vs new) before cutover  

### Debugging tools/methods
- EXPEDITER (Itaú)  
- Abend codes / dump analysis  
- Display/logging in controlled environments  
- Trace of JCL steps and COND codes  
- Reproduce with subset of production-like data  

### Modernization / migration experience
- Not full rewrites, but: RPA wrapping legacy processes; API/integration from legacy to microservices later career; documenting for AI training is a form of knowledge extraction that enables modernization without big-bang rewrite.

### Languages / communication
> I can write precise English technical documentation. Spoken English is professional working level. Happy to work async in English with written-first collaboration.

## 5. Coding exercise tips

Expect pseudo-COBOL or short COBOL snippets:
- IDENTIFICATION / ENVIRONMENT / DATA / PROCEDURE DIVISION  
- PIC clauses, COMP-3, REDEFINES, OCCURS  
- PERFORM UNTIL / VARYING  
- File OPEN/READ/WRITE/CLOSE, FILE STATUS  
- EVALUATE TRUE, nested IF  
- Call subprograms, linkage section  
- SQL COBOL (EXEC SQL) basics if asked  

**Talk while solving:** state assumptions, edge cases, what you’d unit-test.

## 6. Checklist before “Take the interview”

- [ ] Quiet room, stable internet  
- [ ] Laptop/desktop (not only phone)  
- [ ] Chrome/Brave updated  
- [ ] Camera + mic allowed  
- [ ] Screen share allowed  
- [ ] Resume PDF open for reference  
- [ ] This prep open in second monitor  
- [ ] Water, 53 min free  

## 7. Links

- Job post: https://jobs.micro1.ai/post/066c86e4-2e57-401f-8d90-406100ac6321  
- Success page / interview CTA: https://jobs.micro1.ai/post/success  
- Interview: https://www.interview.micro1.ai/intro/micro1/?candidate=37cb9220-550d-4072-b837-471a943fa44d&ping=ok  
- Support: support@micro1.ai  
