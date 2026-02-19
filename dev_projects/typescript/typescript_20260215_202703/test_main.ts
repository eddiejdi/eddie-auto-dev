import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';

interface JiraIssue {
  key: string;
  fields: {
    summary: string;
    description: string;
    status: {
      name: string;
    };
  };
}

class JiraService {
  private apiUrl = 'https://your-jira-instance.atlassian.net/rest/api/3';
  private token: string;

  constructor(token: string) {
    this.token = token;
  }

  async createIssue(summary: string, description: string): Promise<JiraIssue> {
    const issueData = {
      fields: {
        summary,
        description,
        project: { key: 'YOUR_PROJECT_KEY' },
        issuetype: { name: 'Task' },
        priority: { name: 'High' },
      },
    };

    try {
      const response = await axios.post<JiraIssue>(
        `${this.apiUrl}/issue`,
        issueData,
        {
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${this.token}`,
          },
        }
      );

      return response.data;
    } catch (error) {
      throw new Error(`Failed to create Jira issue: ${error.message}`);
    }
  }

  async updateIssue(issueKey: string, summary?: string, description?: string): Promise<JiraIssue> {
    const issueData = {};

    if (summary) {
      issueData.summary = summary;
    }

    if (description) {
      issueData.description = description;
    }

    try {
      const response = await axios.put<JiraIssue>(
        `${this.apiUrl}/issue/${issueKey}`,
        issueData,
        {
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${this.token}`,
          },
        }
      );

      return response.data;
    } catch (error) {
      throw new Error(`Failed to update Jira issue: ${error.message}`);
    }
  }

  async getIssue(issueKey: string): Promise<JiraIssue> {
    try {
      const response = await axios.get<JiraIssue>(
        `${this.apiUrl}/issue/${issueKey}`,
        {
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${this.token}`,
          },
        }
      );

      return response.data;
    } catch (error) {
      throw new Error(`Failed to get Jira issue: ${error.message}`);
    }
  }

  async closeIssue(issueKey: string): Promise<void> {
    try {
      await axios.put<JiraIssue>(
        `${this.apiUrl}/issue/${issueKey}/status`,
        { statusId: '10200' }, // ID do status "Closed"
        {
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${this.token}`,
          },
        }
      );
    } catch (error) {
      throw new Error(`Failed to close Jira issue: ${error.message}`);
    }
  }
}

class TypeScriptAgent {
  private token: string;
  private jiraService: JiraService;

  constructor(token: string, jiraService: JiraService) {
    this.token = token;
    this.jiraService = jiraService;
  }

  async registerEvent(eventType: string, eventData: any): Promise<void> {
    const eventId = uuidv4();
    const eventDetails = { ...eventData, eventType };

    try {
      await axios.post('https://your-event-tracking-service.com/register', {
        id: eventId,
        details: eventDetails,
      }, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.token}`,
        },
      });
    } catch (error) {
      throw new Error(`Failed to register event: ${error.message}`);
    }
  }

  async monitorActivity(): Promise<void> {
    try {
      const issues = await this.jiraService.getIssue('YOUR_ISSUE_KEY');
      console.log('Current Jira issue:', issues);

      // Simulação de atualização do status
      await this.jiraService.updateIssue('YOUR_ISSUE_KEY', 'Updated by TypeScript Agent');

      // Simulação de fechamento do issue
      await this.jiraService.closeIssue('YOUR_ISSUE_KEY');
    } catch (error) {
      console.error('Failed to monitor activity:', error.message);
    }
  }

  async main(): Promise<void> {
    try {
      const token = 'YOUR_JIRA_TOKEN';
      const jiraService = new JiraService(token);

      await this.registerEvent('ActivityMonitoringStarted', { eventType: 'start' });
      await this.monitorActivity();
      await this.registerEvent('ActivityMonitoringStopped', { eventType: 'stop' });
    } catch (error) {
      console.error('Main function failed:', error.message);
    }
  }
}

// Execução do programa
const token = 'YOUR_JIRA_TOKEN';
const jiraService = new JiraService(token);

const agent = new TypeScriptAgent(token, jiraService);
agent.main();