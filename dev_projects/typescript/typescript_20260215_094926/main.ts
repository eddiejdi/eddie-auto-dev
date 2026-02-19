import { JiraClient } from 'jira-client';
import { Logger } from 'winston';

// Configuração do Winston para logs
const logger = new Logger({
  level: 'info',
  format: {
    json: true,
  },
});

// Classe para representar um item de atividade
class ActivityItem {
  constructor(public title: string, public description: string) {}
}

// Interface para representar uma atividade
interface Activity {
  id: number;
  title: string;
  description: string;
  logs: Log[];
}

// Interface para representar um log
interface Log {
  message: string;
  timestamp: Date;
}

// Classe para representar um relatório de atividades
class ActivityReport {
  constructor(public activities: Activity[]) {}
}

// Classe para representar o cliente do Jira
class JiraClientImpl implements JiraClient {
  private jiraUrl: string;
  private username: string;
  private password: string;

  constructor(jiraUrl: string, username: string, password: string) {
    this.jiraUrl = jiraUrl;
    this.username = username;
    this.password = password;
  }

  async getActivities(): Promise<Activity[]> {
    try {
      const response = await fetch(`${this.jiraUrl}/rest/api/2/search?jql=project=myProject`, {
        method: 'GET',
        headers: {
          'Authorization': `Basic ${btoa(`${this.username}:${this.password}`)}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data.items.map(item => ({
        id: item.id,
        title: item.fields.summary,
        description: item.fields.description,
        logs: [],
      }));
    } catch (error) {
      logger.error('Error fetching activities:', error);
      throw new Error(`Failed to fetch activities: ${error.message}`);
    }
  }

  async logActivity(activityId: number, message: string): Promise<void> {
    try {
      const response = await fetch(`${this.jiraUrl}/rest/api/2/issue/${activityId}/comment`, {
        method: 'POST',
        headers: {
          'Authorization': `Basic ${btoa(`${this.username}:${this.password}`)}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ body: message }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      logger.info('Activity logged successfully');
    } catch (error) {
      logger.error('Error logging activity:', error);
      throw new Error(`Failed to log activity: ${error.message}`);
    }
  }

  async getLogs(activityId: number): Promise<Log[]> {
    try {
      const response = await fetch(`${this.jiraUrl}/rest/api/2/issue/${activityId}/comment`, {
        method: 'GET',
        headers: {
          'Authorization': `Basic ${btoa(`${this.username}:${this.password}`)}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data.comments.map(comment => ({
        message: comment.body,
        timestamp: new Date(comment.created),
      }));
    } catch (error) {
      logger.error('Error fetching logs:', error);
      throw new Error(`Failed to fetch logs: ${error.message}`);
    }
  }

  async generateReport(activities: Activity[]): Promise<ActivityReport> {
    try {
      const report = new ActivityReport(activities);

      // Implemente aqui a lógica para gerar o relatório
      // Por exemplo, você pode criar um arquivo CSV com os detalhes das atividades

      logger.info('Report generated successfully');
      return report;
    } catch (error) {
      logger.error('Error generating report:', error);
      throw new Error(`Failed to generate report: ${error.message}`);
    }
  }
}

// Função main para executar o script
async function main() {
  try {
    const jiraClient = new JiraClientImpl(
      'https://your-jira-instance.atlassian.net',
      'your-username',
      'your-password',
    );

    const activities = await jiraClient.getActivities();
    logger.info('Activities fetched:', activities);

    const report = await jiraClient.generateReport(activities);
    logger.info('Report generated:', report);
  } catch (error) {
    logger.error('Error executing the script:', error);
  }
}

if (require.main === module) {
  main().catch(error => console.error(error));
}