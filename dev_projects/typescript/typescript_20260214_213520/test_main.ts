import { JiraClient } from 'jira-client';
import { expect } from 'chai';

describe('TypeScriptAgent', () => {
    let agent: TypeScriptAgent;

    beforeEach(() => {
        agent = new TypeScriptAgent('https://your-jira-host.com');
    });

    describe('#monitorActivities', () => {
        it('should monitor activities successfully', async () => {
            const issues = await agent.monitorActivities();
            expect(issues).to.have.lengthOf.above(0);
        });

        it('should handle errors gracefully', async () => {
            jest.spyOn(agent.jiraClient, 'search').mockImplementationOnce(() => Promise.reject(new Error('Mocked error')));
            try {
                await agent.monitorActivities();
            } catch (error) {
                expect(error).to.have.property('message', 'Mocked error');
            }
        });
    });

    describe('#registerEvent', () => {
        it('should register an event successfully', async () => {
            const result = await agent.registerEvent('New feature implemented');
            expect(result).to.equal('New feature implemented');
        });

        it('should handle errors gracefully', async () => {
            jest.spyOn(agent.jiraClient, 'createIssue').mockImplementationOnce(() => Promise.reject(new Error('Mocked error')));
            try {
                await agent.registerEvent('New feature implemented');
            } catch (error) {
                expect(error).to.have.property('message', 'Mocked error');
            }
        });
    });

    describe('#main', () => {
        it('should execute the main function successfully', async () => {
            const result = await agent.main();
            expect(result).to.equal('Main executed');
        });

        it('should handle errors gracefully', async () => {
            jest.spyOn(agent.jiraClient, 'search').mockImplementationOnce(() => Promise.reject(new Error('Mocked error')));
            try {
                await agent.main();
            } catch (error) {
                expect(error).to.have.property('message', 'Mocked error');
            }
        });
    });
});