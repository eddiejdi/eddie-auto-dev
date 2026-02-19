using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraNet;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do Jira
        var jira = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        // Função para criar uma tarefa no Jira
        async Task CreateTaskAsync(string projectKey, string summary, string description)
        {
            var task = await jira.CreateIssueAsync(projectKey, new Issue
            {
                Summary = summary,
                Description = description
            });

            Console.WriteLine($"Tarefa criada com ID: {task.Id}");
        }

        // Função para monitorar atividades do usuário no Jira
        async Task MonitorUserActivityAsync(string username)
        {
            var issues = await jira.SearchIssuesAsync(username, "status in (Open, In Progress)");

            foreach (var issue in issues)
            {
                Console.WriteLine($"Issue ID: {issue.Id}, Summary: {issue.Summary}");
            }
        }

        // Função para gerenciar tarefas no Jira
        async Task ManageTasksAsync(string projectKey, string username)
        {
            var issues = await jira.SearchIssuesAsync(username, "status in (Open, In Progress)");

            foreach (var issue in issues)
            {
                Console.WriteLine($"Issue ID: {issue.Id}, Summary: {issue.Summary}");

                // Exemplo de atualização de status
                var updatedIssue = await jira.UpdateIssueAsync(issue.Key, new Issue
                {
                    Status = "In Progress"
                });

                Console.WriteLine($"Tarefa atualizada com novo status: {updatedIssue.Status}");
            }
        }

        // Função principal para executar as funcionalidades
        async Task MainAsync()
        {
            await CreateTaskAsync("YOUR_PROJECT_KEY", "Teste de Tarefa", "Descrição da tarefa");
            await MonitorUserActivityAsync("username");
            await ManageTasksAsync("YOUR_PROJECT_KEY", "username");
        }

        // Executa a função principal
        MainAsync();
    }
}