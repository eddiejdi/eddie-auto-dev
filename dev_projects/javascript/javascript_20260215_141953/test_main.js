const axios = require('axios');
const { JiraClient } = require('@jira/client');

// Classe para representar a atividade em JavaScript
class Activity {
    constructor(id, title, description) {
        this.id = id;
        this.title = title;
        this.description = description;
    }
}

// Função para criar uma nova atividade no Jira
async function createActivity(jiraClient, activity) {
    try {
        const response = await jiraClient.request({
            method: 'POST',
            url: '/rest/api/2/issue',
            headers: {
                'Content-Type': 'application/json'
            },
            data: {
                fields: {
                    project: { key: 'YOUR_PROJECT_KEY' },
                    summary: activity.title,
                    description: activity.description
                }
            }
        });

        console.log('Activity created:', response.data.key);
    } catch (error) {
        console.error('Error creating activity:', error);
    }
}

// Função para monitorar atividades em JavaScript
async function monitorActivities(jiraClient, activities) {
    for (const activity of activities) {
        await createActivity(jiraClient, activity);
        // Aguarda 10 segundos antes de criar a próxima atividade
        await new Promise(resolve => setTimeout(resolve, 10000));
    }
}

// Função principal para executar o scrum-9
async function main() {
    try {
        const jiraClient = new JiraClient({
            auth: {
                username: 'YOUR_USERNAME',
                password: 'YOUR_PASSWORD'
            },
            host: 'https://your-jira-instance.atlassian.net'
        });

        // Lista de atividades em JavaScript
        const activities = [
            new Activity('12345', 'Criar um novo projeto', 'Crie um novo projeto no Jira'),
            new Activity('67890', 'Atualizar o status da tarefa', 'Atualize o status da tarefa para "Em andamento"')
        ];

        // Monitora as atividades
        await monitorActivities(jiraClient, activities);
    } catch (error) {
        console.error('Error running scrum-9:', error);
    }
}

// Executa a função principal se o script for executado como um programa
if (require.main === module) {
    main();
}