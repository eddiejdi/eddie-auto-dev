import { JiraClient } from 'jira-client';

// Define a classe para representar uma atividade em TypeScript
class Activity {
  constructor(public id: number, public title: string) {}
}

// Define a função principal para executar o scrum-10
async function main() {
  try {
    // Crie um cliente Jira usando as credenciais fornecidas
    const jiraClient = new JiraClient({
      url: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password'
    });

    // Define a função para criar uma atividade em Jira
    async function createActivity(activity: Activity): Promise<void> {
      const response = await jiraClient.createIssue({
        fields: {
          project: { key: 'YOUR_PROJECT_KEY' },
          summary: activity.title,
          description: `ID: ${activity.id}`
        }
      });

      console.log(`Activity created with ID: ${response.id}`);
    }

    // Define a função para listar todas as atividades em Jira
    async function listActivities(): Promise<void> {
      const response = await jiraClient.searchIssues({
        jql: 'project = YOUR_PROJECT_KEY',
        fields: ['id', 'summary']
      });

      response.issues.forEach(issue => {
        console.log(`Activity ID: ${issue.id}, Summary: ${issue.fields.summary}`);
      });
    }

    // Crie uma atividade
    const newActivity = new Activity(123, 'New TypeScript Activity');
    await createActivity(newActivity);

    // Listar todas as atividades
    await listActivities();
  } catch (error) {
    console.error('Error:', error);
  }
}

// Execute a função main()
if (require.main === module) {
  main();
}