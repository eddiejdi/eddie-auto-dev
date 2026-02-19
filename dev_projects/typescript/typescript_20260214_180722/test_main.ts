import { JiraClient } from 'jira-client';
import { Agent } from './agent';

describe('TypeScriptAgent', () => {
    let jiraClient: JiraClient;
    let agent: TypeScriptAgent;

    beforeEach(() => {
        jiraClient = new JiraClient({
            url: 'https://your-jira-instance.atlassian.net',
            username: 'your-username',
            password: 'your-password'
        });
        agent = new TypeScriptAgent(jiraClient);
    });

    describe('trackActivity', () => {
        it('should track activity for a valid issue key and description', async () => {
            await agent.trackActivity('ABC-123', 'This is a test activity');
            expect(console.log).toHaveBeenCalledWith(`Activity tracked for issue ABC-123`);
        });

        it('should throw an error if the issue key is invalid', async () => {
            try {
                await agent.trackActivity('invalid-key', 'This is a test activity');
            } catch (error) {
                expect(error.message).toContain('Error tracking activity:');
                expect(error.message).toContain('Invalid issue key: invalid-key');
            }
        });

        it('should throw an error if the description is empty', async () => {
            try {
                await agent.trackActivity('ABC-123', '');
            } catch (error) {
                expect(error.message).toContain('Error tracking activity:');
                expect(error.message).toContain('Invalid issue key: ABC-123');
            }
        });
    });

    describe('getIssues', () => {
        it('should return an array of issue keys for a valid project', async () => {
            const issues = await agent.getIssues();
            expect(issues.length).toBeGreaterThan(0);
            expect(Array.isArray(issues)).toBeTruthy();
        });

        it('should throw an error if the project key is invalid', async () => {
            try {
                await agent.getIssues('invalid-project-key');
            } catch (error) {
                expect(error.message).toContain('Error fetching issues:');
                expect(error.message).toContain('Invalid project key: invalid-project-key');
            }
        });
    });
});