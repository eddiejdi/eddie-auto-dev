import { expect } from 'chai';
import { JiraTypeScriptAgent } from './JiraTypeScriptAgent';

describe('JiraTypeScriptAgent', () => {
    describe('startTrackingIssue', () => {
        it('should start tracking an issue with a valid issue key', async () => {
            const agent = new JiraTypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
            await agent.startTrackingIssue('ABC-123');
            expect(console.log).to.have.been.calledWith(`Tracking issue ABC-123 started.`);
        });

        it('should throw an error if the issue key is invalid', async () => {
            const agent = new JiraTypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
            await expect(agent.startTrackingIssue('invalid-key')).to.be.rejectedWith('Error starting tracking issue: Invalid issue key.');
        });
    });

    describe('stopTrackingIssue', () => {
        it('should stop tracking an issue with a valid issue key', async () => {
            const agent = new JiraTypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
            await agent.startTrackingIssue('ABC-123');
            await agent.stopTrackingIssue('ABC-123');
            expect(console.log).to.have.been.calledWith(`Tracking issue ABC-123 stopped.`);
        });

        it('should throw an error if the issue key is invalid', async () => {
            const agent = new JiraTypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
            await expect(agent.stopTrackingIssue('invalid-key')).to.be.rejectedWith('Error stopping tracking issue: Invalid issue key.');
        });
    });

    describe('updateIssueStatus', () => {
        it('should update the status of an issue with a valid issue key and new status', async () => {
            const agent = new JiraTypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
            await agent.startTrackingIssue('ABC-123');
            await agent.updateIssueStatus('ABC-123', 'In Progress');
            expect(console.log).to.have.been.calledWith(`Updated status of issue ABC-123 to In Progress.`);
        });

        it('should throw an error if the issue key is invalid', async () => {
            const agent = new JiraTypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
            await expect(agent.updateIssueStatus('invalid-key', 'In Progress')).to.be.rejectedWith('Error updating issue status: Invalid issue key.');
        });

        it('should throw an error if the new status is invalid', async () => {
            const agent = new JiraTypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
            await expect(agent.updateIssueStatus('ABC-123', 'Invalid Status')).to.be.rejectedWith('Error updating issue status: Invalid status.');
        });
    });

    describe('main', () => {
        it('should start tracking an issue, update its status, and stop tracking it', async () => {
            const agent = new JiraTypeScriptAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
            await agent.main();
            expect(console.log).to.have.been.calledWith(`Tracking issue ABC-123 started.`);
            expect(console.log).to.have.been.calledWith(`Updated status of issue ABC-123 to In Progress.`);
            expect(console.log).to.have.been.calledWith(`Tracking issue ABC-123 stopped.`);
        });
    });
});