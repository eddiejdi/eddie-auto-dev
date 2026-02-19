import { JiraClient } from 'jira-client';
import { expect } from 'chai';

describe('JiraIntegration', () => {
    let jiraClient: JiraClient;

    beforeEach(() => {
        jiraClient = new JiraClient({
            url: 'https://your-jira-instance.atlassian.net',
            auth: {
                username: 'YOUR_USERNAME',
                password: 'YOUR_PASSWORD'
            }
        });
    });

    describe('logActivity', () => {
        it('should log activity successfully with a valid issue key and activity message', async () => {
            await jiraClient.addCommentToIssue('YOUR_ISSUE_KEY', 'Starting development');
            expect(console.log).to.have.been.calledWith(`Logged activity: Starting development`);
        });

        it('should throw an error if the issue key is invalid', async () => {
            try {
                await jiraClient.addCommentToIssue('INVALID_KEY', 'Starting development');
            } catch (error) {
                expect(error.message).to.equal('Error logging activity: Invalid issue key');
            }
        });
    });

    describe('monitorActivity', () => {
        it('should monitor issues with a valid JQL query and log the key of each issue', async () => {
            const issues = await jiraClient.searchIssues({
                jql: 'status = "In Progress"'
            });
            for (const issue of issues.issues) {
                expect(console.log).to.have.been.calledWith(`Monitoring issue: ${issue.key}`);
            }
        });

        it('should throw an error if the JQL query is invalid', async () => {
            try {
                await jiraClient.searchIssues({
                    jql: 'INVALID_QUERY'
                });
            } catch (error) {
                expect(error.message).to.equal('Error monitoring activities: Invalid JQL query');
            }
        });
    });

    describe('registerLogs', () => {
        it('should register logs for issues with a valid JQL query and log the key of each issue', async () => {
            const issues = await jiraClient.searchIssues({
                jql: 'status = "Completed"'
            });
            for (const issue of issues.issues) {
                expect(console.log).to.have.been.calledWith(`Registering log for issue: ${issue.key}`);
            }
        });

        it('should throw an error if the JQL query is invalid', async () => {
            try {
                await jiraClient.searchIssues({
                    jql: 'INVALID_QUERY'
                });
            } catch (error) {
                expect(error.message).to.equal('Error registering logs: Invalid JQL query');
            }
        });
    });

    describe('main', () => {
        it('should log activity, monitor activities, and register logs successfully with valid credentials', async () => {
            await jiraClient.addCommentToIssue('YOUR_ISSUE_KEY', 'Starting development');
            await jiraClient.searchIssues({
                jql: 'status = "In Progress"'
            });
            await jiraClient.searchIssues({
                jql: 'status = "Completed"'
            });
        });

        it('should throw an error if the credentials are invalid', async () => {
            try {
                const integration = new JiraIntegration('https://your-jira-instance.atlassian.net', 'INVALID_USERNAME', 'INVALID_PASSWORD');
                await integration.main();
            } catch (error) {
                expect(error.message).to.equal('Error logging activity: Invalid credentials');
            }
        });
    });
});