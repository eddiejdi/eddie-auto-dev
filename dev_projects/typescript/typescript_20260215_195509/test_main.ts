import { JiraClient } from 'jira-client';
import { Agent } from 'typescript-agent';

describe('JiraIntegration', () => {
    let jiraClient: JiraClient;
    let agent: Agent;

    beforeEach(() => {
        jiraHost = 'https://your-jira-host.com';
        username = 'your-username';
        password = 'your-password';

        jiraClient = new JiraClient({
            host: jiraHost,
            auth: { username, password }
        });

        agent = new Agent(jiraClient);
    });

    describe('startTracking', () => {
        it('should start tracking an issue with a valid issue key', async () => {
            await integration.startTracking('ABC-123');
            expect(console.log).toHaveBeenCalledWith(`Activity tracking started for issue ABC-123`);
        });

        it('should handle errors when starting tracking an issue', async () => {
            try {
                await integration.startTracking('invalid-issue-key');
            } catch (error) {
                expect(error.message).toContain('Error starting activity tracking');
            }
        });
    });

    describe('stopTracking', () => {
        it('should stop tracking an issue with a valid issue key', async () => {
            await integration.stopTracking('ABC-123');
            expect(console.log).toHaveBeenCalledWith(`Activity tracking stopped for issue ABC-123`);
        });

        it('should handle errors when stopping tracking an issue', async () => {
            try {
                await integration.stopTracking('invalid-issue-key');
            } catch (error) {
                expect(error.message).toContain('Error stopping activity tracking');
            }
        });
    });
});