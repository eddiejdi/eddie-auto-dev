import { Agent } from 'http';
import { IncomingMessage } from 'http';

class JiraClient {
    private url: string;
    private token: string;

    constructor(url: string, token: string) {
        this.url = url;
        this.token = token;
    }

    async createIssue(title: string, description: string): Promise<void> {
        const options = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Basic ${btoa(`${this.token}:x`)}`
            },
            body: JSON.stringify({
                fields: {
                    project: { key: 'YOUR_PROJECT_KEY' },
                    summary: title,
                    description: description
                }
            })
        };

        const response = await fetch(this.url, options);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        console.log('Issue created successfully');
    }
}

class TypeScriptAgent {
    private agent: Agent;
    private url: string;

    constructor(url: string) {
        this.url = url;
        this.agent = new Agent();
    }

    async sendToJira(title: string, description: string): Promise<void> {
        const client = new JiraClient(this.url, 'YOUR_JIRA_TOKEN');
        await client.createIssue(title, description);
    }
}

async function main() {
    const agent = new TypeScriptAgent('https://your-jira-instance.atlassian.net/rest/api/2.0/issue');
    try {
        await agent.sendToJira('Test Issue', 'This is a test issue created using TypeScript Agent with Jira.');
    } catch (error) {
        console.error(error);
    }
}

if (require.main === module) {
    main();
}