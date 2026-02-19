import { JiraClient } from 'jira-client';
import { Logger } from 'winston';

// Configuração do logger
const logger = new Logger({
  level: 'info',
  format: 'json'
});

// Função para conectar ao Jira
async function connectToJira(): Promise<JiraClient> {
  const jiraClient = new JiraClient({
    url: 'https://your-jira-instance.atlassian.net/rest/api/3',
    username: 'your-username',
    password: 'your-password'
  });
  await jiraClient.login();
  return jiraClient;
}

// Função para registrar logs
async function logActivity(jiraClient: JiraClient, issueKey: string, message: string): Promise<void> {
  try {
    const issue = await jiraClient.issue.get(issueKey);
    logger.info(`Logged activity for issue ${issueKey}: ${message}`);
  } catch (error) {
    logger.error(`Error logging activity for issue ${issueKey}:`, error);
  }
}

// Função principal
async function main(): Promise<void> {
  try {
    // Conectar ao Jira
    const jiraClient = await connectToJira();

    // Registrar atividade em um issue específico
    const issueKey = 'ABC-123';
    const message = 'User logged in successfully.';
    await logActivity(jiraClient, issueKey, message);

    logger.info('Scrum-10 completed successfully.');
  } catch (error) {
    logger.error('An error occurred during Scrum-10:', error);
  }
}

// Executar o programa
if (require.main === module) {
  main().catch(error => {
    console.error('Error running the program:', error);
  });
}