import { JiraService } from './jira.service';
import { TypeScriptAgent } from './typescript-agent';

class Scrum10 {
    private jiraService: JiraService;
    private typeScriptAgent: TypeScriptAgent;

    constructor() {
        this.jiraService = new JiraService();
        this.typeScriptAgent = new TypeScriptAgent();
    }

    async startScrumProcess(): Promise<void> {
        try {
            console.log('Starting Scrum Process...');
            await this.jiraService.createProject('TypeScript Project');
            await this.jiraService.createSprint('Sprint 1', '2023-04-01', '2023-04-15');
            await this.typeScriptAgent.configureServices();
            console.log('Scrum Process started successfully!');
        } catch (error) {
            console.error('Error starting Scrum Process:', error);
        }
    }

    async monitorRealTime(): Promise<void> {
        try {
            console.log('Monitoring Real-Time...');
            const issues = await this.jiraService.getIssuesInSprint('TypeScript Project', 'Sprint 1');
            console.log('Real-time monitoring complete!');
            // Process issues as needed
        } catch (error) {
            console.error('Error monitoring real-time:', error);
        }
    }

    async main(): Promise<void> {
        try {
            await this.startScrumProcess();
            await this.monitorRealTime();
        } finally {
            console.log('Scrum process completed.');
        }
    }
}

// Execute the main function if the script is run directly
if (require.main === module) {
    new Scrum10().main();
}