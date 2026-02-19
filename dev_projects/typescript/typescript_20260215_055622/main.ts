import { JiraClient } from 'jira-client';
import { TypeScriptAgent } from 'typescript-agent';

class JiraIntegration {
    private jiraClient: JiraClient;

    constructor(jiraUrl: string, username: string, password: string) {
        this.jiraClient = new JiraClient({
            url: jiraUrl,
            username: username,
            password: password
        });
    }

    async createIssue(title: string, description: string): Promise<void> {
        try {
            const issue = await this.jiraClient.createIssue({
                fields: {
                    project: { key: 'YOUR_PROJECT_KEY' },
                    summary: title,
                    description: description
                }
            });

            console.log(`Issue created with ID ${issue.id}`);
        } catch (error) {
            console.error('Error creating issue:', error);
        }
    }

    async updateIssue(issueId: string, title?: string, description?: string): Promise<void> {
        try {
            const updatedFields = {};
            if (title) updatedFields.summary = title;
            if (description) updatedFields.description = description;

            await this.jiraClient.updateIssue(issueId, updatedFields);

            console.log(`Issue ${issueId} updated`);
        } catch (error) {
            console.error('Error updating issue:', error);
        }
    }

    async deleteIssue(issueId: string): Promise<void> {
        try {
            await this.jiraClient.deleteIssue(issueId);

            console.log(`Issue ${issueId} deleted`);
        } catch (error) {
            console.error('Error deleting issue:', error);
        }
    }
}

class TypeScriptAgentIntegration {
    private agent: TypeScriptAgent;

    constructor(token: string, url: string) {
        this.agent = new TypeScriptAgent({
            token,
            url
        });
    }

    async executeScript(script: string): Promise<void> {
        try {
            await this.agent.executeScript(script);

            console.log('Script executed successfully');
        } catch (error) {
            console.error('Error executing script:', error);
        }
    }
}

async function main() {
    const jiraUrl = 'https://your-jira-instance.atlassian.net';
    const username = 'your-username';
    const password = 'your-password';

    const jiraIntegration = new JiraIntegration(jiraUrl, username, password);

    await jiraIntegration.createIssue('TypeScript Agent Integration', 'This is a test issue for TypeScript Agent integration with Jira.');

    // Update the issue
    await jiraIntegration.updateIssue('12345', 'Updated title', 'Updated description');

    // Delete the issue
    await jiraIntegration.deleteIssue('12345');

    const token = 'your-token';
    const url = 'https://your-typescript-agent-instance.com';

    const agentIntegration = new TypeScriptAgentIntegration(token, url);

    await agentIntegration.executeScript('console.log("Hello from TypeScript Agent!");');
}

if (require.main === module) {
    main().catch((error) => {
        console.error('Error:', error);
    });
}