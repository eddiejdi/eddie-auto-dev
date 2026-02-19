import axios from 'axios';
import { JiraClient } from './jira-client';

interface Event {
  id: string;
  type: string;
  data: any;
}

class TypeScriptAgent implements JiraClient {
  private apiUrl: string = 'https://your-jira-instance.atlassian.net/rest/api/3/project/{projectId}/issue/{issueId}/comment';
  private token: string;

  constructor(token: string) {
    this.token = token;
  }

  async createEvent(event: Event): Promise<void> {
    try {
      const response = await axios.post(this.apiUrl, event, {
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        }
      });
      console.log('Event created successfully:', response.data);
    } catch (error) {
      console.error('Error creating event:', error);
    }
  }

  async getEvents(projectId: string, issueId: string): Promise<Event[]> {
    try {
      const response = await axios.get(this.apiUrl.replace('{issueId}', issueId), {
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        }
      });
      return response.data;
    } catch (error) {
      console.error('Error getting events:', error);
      return [];
    }
  }

  async main(): Promise<void> {
    const token = process.env.JIRA_TOKEN!;
    const client = new TypeScriptAgent(token);

    try {
      const event: Event = {
        id: '12345',
        type: 'bug',
        data: {
          title: 'Bug in TypeScript code',
          description: 'The TypeScript code is not compiling correctly'
        }
      };

      await client.createEvent(event);
      console.log('Event created:', event);

      const events = await client.getEvents('YOUR_PROJECT_ID', 'YOUR_ISSUE_ID');
      console.log('Events:', events);
    } catch (error) {
      console.error('Error in main:', error);
    }
  }
}

if (require.main === module) {
  TypeScriptAgent.main();
}