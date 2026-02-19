import { JiraClient } from 'jira-client';
import { expect } from 'chai';

class TypeScriptAgent {
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
            await this.jiraClient.createIssue({
                fields: {
                    summary: title,
                    description: description
                }
            });
            console.log('Issue created successfully');
        } catch (error) {
            console.error('Error creating issue:', error);
        }
    }

    async updateIssue(issueId: string, title: string, description: string): Promise<void> {
        try {
            await this.jiraClient.updateIssue({
                issueId,
                fields: {
                    summary: title,
                    description: description
                }
            });
            console.log('Issue updated successfully');
        } catch (error) {
            console.error('Error updating issue:', error);
        }
    }

    async closeIssue(issueId: string): Promise<void> {
        try {
            await this.jiraClient.updateIssue({
                issueId,
                fields: {
                    status: 'Closed'
                }
            });
            console.log('Issue closed successfully');
        } catch (error) {
            console.error('Error closing issue:', error);
        }
    }

    async getIssues(): Promise<Array<any>> {
        try {
            const issues = await this.jiraClient.getIssues();
            return issues;
        } catch (error) {
            console.error('Error fetching issues:', error);
            return [];
        }
    }
}

describe('TypeScriptAgent', () => {
    describe('createIssue', () => {
        it('should create an issue with valid title and description', async () => {
            const jiraUrl = 'https://your-jira-instance.atlassian.net';
            const username = 'your-username';
            const password = 'your-password';

            const agent = new TypeScriptAgent(jiraUrl, username, password);

            await agent.createIssue('New TypeScript Issue', 'This is a test issue created by TypeScript Agent');
        });

        it('should throw an error if the title or description is empty', async () => {
            const jiraUrl = 'https://your-jira-instance.atlassian.net';
            const username = 'your-username';
            const password = 'your-password';

            const agent = new TypeScriptAgent(jiraUrl, username, password);

            await expect(agent.createIssue('', '')).to.rejectedWith('Title and description cannot be empty');
        });
    });

    describe('updateIssue', () => {
        it('should update an issue with valid title and description', async () => {
            const jiraUrl = 'https://your-jira-instance.atlassian.net';
            const username = 'your-username';
            const password = 'your-password';

            const agent = new TypeScriptAgent(jiraUrl, username, password);

            await agent.createIssue('New TypeScript Issue', 'This is a test issue created by TypeScript Agent');
            await agent.updateIssue('1234567890', 'Updated TypeScript Issue', 'This is an updated test issue created by TypeScript Agent');
        });

        it('should throw an error if the issueId or title or description is empty', async () => {
            const jiraUrl = 'https://your-jira-instance.atlassian.net';
            const username = 'your-username';
            const password = 'your-password';

            const agent = new TypeScriptAgent(jiraUrl, username, password);

            await expect(agent.updateIssue('', '', '')).to.rejectedWith('Issue ID, title, and description cannot be empty');
        });
    });

    describe('closeIssue', () => {
        it('should close an issue with valid issueId', async () => {
            const jiraUrl = 'https://your-jira-instance.atlassian.net';
            const username = 'your-username';
            const password = 'your-password';

            const agent = new TypeScriptAgent(jiraUrl, username, password);

            await agent.createIssue('New TypeScript Issue', 'This is a test issue created by TypeScript Agent');
            await agent.closeIssue('1234567890');
        });

        it('should throw an error if the issueId is empty', async () => {
            const jiraUrl = 'https://your-jira-instance.atlassian.net';
            const username = 'your-username';
            const password = 'your-password';

            const agent = new TypeScriptAgent(jiraUrl, username, password);

            await expect(agent.closeIssue('')).to.rejectedWith('Issue ID cannot be empty');
        });
    });

    describe('getIssues', () => {
        it('should fetch all issues successfully', async () => {
            const jiraUrl = 'https://your-jira-instance.atlassian.net';
            const username = 'your-username';
            const password = 'your-password';

            const agent = new TypeScriptAgent(jiraUrl, username, password);

            await agent.createIssue('New TypeScript Issue', 'This is a test issue created by TypeScript Agent');
            const issues = await agent.getIssues();
            expect(issues).to.have.lengthOf.at.least(1);
        });

        it('should throw an error if there are no issues', async () => {
            const jiraUrl = 'https://your-jira-instance.atlassian.net';
            const username = 'your-username';
            const password = 'your-password';

            const agent = new TypeScriptAgent(jiraUrl, username, password);

            await expect(agent.getIssues()).to.rejectedWith('No issues found');
        });
    });
});