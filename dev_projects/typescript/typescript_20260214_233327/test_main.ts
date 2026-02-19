import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/models/issue';

// Configuração do cliente Jira
const jira = new JiraClient({
  options: {
    auth: {
      username: 'your_username',
      password: 'your_password'
    },
    protocol: 'https',
    host: 'your_jira_host',
    port: 443,
    pathPrefix: '/rest/api/2'
  }
});

// Função para criar uma nova tarefa no Jira
async function createIssue(title: string, description: string): Promise<Issue> {
  try {
    const issue = await jira.createIssue({
      fields: {
        summary: title,
        description: description,
        project: { key: 'YOUR_PROJECT_KEY' }
      }
    });
    console.log('Tarefa criada:', issue);
    return issue;
  } catch (error) {
    console.error('Erro ao criar tarefa:', error);
    throw error;
  }
}

// Função para atualizar uma tarefa no Jira
async function updateIssue(issueId: string, title: string, description: string): Promise<Issue> {
  try {
    const issue = await jira.updateIssue({
      fields: {
        summary: title,
        description: description
      },
      id: issueId
    });
    console.log('Tarefa atualizada:', issue);
    return issue;
  } catch (error) {
    console.error('Erro ao atualizar tarefa:', error);
    throw error;
  }
}

// Função para deletar uma tarefa no Jira
async function deleteIssue(issueId: string): Promise<void> {
  try {
    await jira.deleteIssue({
      id: issueId
    });
    console.log('Tarefa deletada com sucesso');
  } catch (error) {
    console.error('Erro ao deletar tarefa:', error);
  }
}

// Função para listar todas as tarefas do projeto
async function listIssues(): Promise<Issue[]> {
  try {
    const issues = await jira.searchIssues({
      jql: 'project=YOUR_PROJECT_KEY',
      fields: ['summary', 'description']
    });
    console.log('Tarefas encontradas:', issues);
    return issues;
  } catch (error) {
    console.error('Erro ao listar tarefas:', error);
    throw error;
  }
}

// Função principal
async function main() {
  try {
    // Criar uma nova tarefa com valores válidos
    const newIssue = await createIssue('Novo Tarefa', 'Descrição da nova tarefa');
    console.log('Tarefa criada com sucesso');

    // Atualizar a tarefa com valores válidos
    await updateIssue(newIssue.id, 'Atualizada Tarefa', 'Nova descrição da tarefa atualizada');

    // Deletar a tarefa com valores válidos
    await deleteIssue(newIssue.id);

    // Listar todas as tarefas do projeto com valores válidos
    const issues = await listIssues();
  } catch (error) {
    console.error('Ocorreu um erro:', error);
  }
}

// Executar o programa
if (require.main === module) {
  main().catch(console.error);
}