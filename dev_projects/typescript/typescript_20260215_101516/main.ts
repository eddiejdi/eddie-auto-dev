import { JiraClient } from 'jira-client';

// Define a interface para representar uma tarefa
interface Task {
  id: string;
  title: string;
  status: string;
}

// Define a classe para representar o cliente do Jira
class JiraClientImpl implements JiraClient {
  private client;

  constructor(jiraUrl: string, username: string, password: string) {
    this.client = new JiraClient({
      url: jiraUrl,
      username: username,
      password: password,
    });
  }

  async getTasks(): Promise<Task[]> {
    const issues = await this.client.getIssues();
    return issues.map(issue => ({
      id: issue.id,
      title: issue.fields.summary,
      status: issue.fields.status.name,
    }));
  }

  async updateTask(taskId: string, newStatus: string): Promise<void> {
    await this.client.updateIssue({
      issueKey: taskId,
      fields: {
        status: { name: newStatus },
      },
    });
  }
}

// Função principal para executar o programa
async function main() {
  const jiraUrl = 'https://your-jira-instance.atlassian.net';
  const username = 'your-username';
  const password = 'your-password';

  const client = new JiraClientImpl(jiraUrl, username, password);

  try {
    const tasks = await client.getTasks();
    console.log('Tasks:', tasks);

    const taskId = 'ABC123'; // Replace with the actual task ID
    const newStatus = 'In Progress'; // Replace with the desired status

    await client.updateTask(taskId, newStatus);
    console.log(`Updated task ${taskId} to ${newStatus}`);
  } catch (error) {
    console.error('Error:', error);
  }
}

// Execute a função main() if this file is run as a script
if (require.main === module) {
  main();
}