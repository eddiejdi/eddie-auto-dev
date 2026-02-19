// Importações necessárias
import { JiraClient } from 'jira-client';
import { Agent } from './agent';

// Classe para representar a integração TypeScript Agent com Jira
class TypeScriptAgentJira {
    private jiraClient: JiraClient;
    private agent: Agent;

    constructor(jiraClient: JiraClient, agent: Agent) {
        this.jiraClient = jiraClient;
        this.agent = agent;
    }

    // Função para iniciar a integração
    async startIntegration() {
        try {
            console.log('Iniciando integração TypeScript Agent com Jira...');
            await this.authenticate();
            await this.createIssue();
            console.log('Integração concluída!');
        } catch (error) {
            console.error('Erro durante a integração:', error);
        }
    }

    // Função para autenticar no Jira
    private async authenticate() {
        try {
            const token = await this.jiraClient.authenticate();
            console.log('Autenticação bem-sucedida!');
            return token;
        } catch (error) {
            throw new Error('Erro ao autenticar no Jira:', error);
        }
    }

    // Função para criar um novo issue no Jira
    private async createIssue() {
        try {
            const token = await this.authenticate();
            const issueData = {
                fields: {
                    project: { key: 'YOUR_PROJECT_KEY' },
                    summary: 'Teste de integração TypeScript Agent com Jira',
                    description: 'Este é um teste para verificar a integração do TypeScript Agent com Jira.',
                    issuetype: { name: 'Bug' }
                }
            };

            const issue = await this.jiraClient.createIssue(token, issueData);
            console.log('Issue criado:', issue.key);
        } catch (error) {
            throw new Error('Erro ao criar o issue no Jira:', error);
        }
    }
}

// Função principal para executar a integração
async function main() {
    try {
        const jiraClient = new JiraClient({
            url: 'https://your-jira-instance.atlassian.net',
            username: 'YOUR_USERNAME',
            password: 'YOUR_PASSWORD'
        });

        const agent = new Agent();

        const integration = new TypeScriptAgentJira(jiraClient, agent);
        await integration.startIntegration();
    } catch (error) {
        console.error('Erro principal:', error);
    }
}

// Verifica se o script é executado diretamente
if (require.main === module) {
    main();
}