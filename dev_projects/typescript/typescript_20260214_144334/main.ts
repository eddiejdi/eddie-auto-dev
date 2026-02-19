// Importações necessárias
import { JiraClient } from 'jira-client';
import { TypeScriptAgent } from './TypeScriptAgent';

// Classe principal do programa
class Main {
    private jira: JiraClient;
    private agent: TypeScriptAgent;

    constructor() {
        this.jira = new JiraClient({
            url: 'https://your-jira-instance.atlassian.net',
            username: 'your-username',
            password: 'your-password'
        });
        this.agent = new TypeScriptAgent(this.jira);
    }

    async main(): Promise<void> {
        try {
            // Iniciar o monitoramento
            await this.agent.startMonitoring();

            console.log('Monitoramento iniciado!');
        } catch (error) {
            console.error('Erro ao iniciar monitoramento:', error);
        }
    }

    static run(): void {
        const main = new Main();
        main.main().catch(error => console.error('Ocorreu um erro durante a execução do programa:', error));
    }
}

// Executar o programa
if (require.main === module) {
    Main.run();
}