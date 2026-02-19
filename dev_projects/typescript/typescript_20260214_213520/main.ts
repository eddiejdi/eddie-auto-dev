import { JiraClient } from 'jira-client';

class TypeScriptAgent {
    private jiraClient: JiraClient;

    constructor(jiraHost: string) {
        this.jiraClient = new JiraClient({
            host: jiraHost,
            auth: {
                username: process.env.JIRA_USERNAME,
                password: process.env.JIRA_PASSWORD
            }
        });
    }

    async monitorActivities() {
        try {
            const issues = await this.jiraClient.search({ jql: 'project = TS' });
            console.log('Issues:', issues);
        } catch (error) {
            console.error('Error monitoring activities:', error);
        }
    }

    async registerEvent(event: string) {
        try {
            await this.jiraClient.createIssue({
                project: { key: 'TS' },
                summary: `New event: ${event}`,
                description: `This is a new event logged by the TypeScript Agent`
            });
            console.log('Event registered:', event);
        } catch (error) {
            console.error('Error registering event:', error);
        }
    }

    async main() {
        await this.monitorActivities();
        await this.registerEvent('New feature implemented');
    }
}

if (require.main === module) {
    const agent = new TypeScriptAgent('https://your-jira-host.com');
    agent.main();
}