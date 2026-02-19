using System;
using System.Net.Http;
using System.Threading.Tasks;
using JiraNetCore.Client;
using JiraNetCore.Models;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do cliente Jira
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Cria uma nova tarefa
        var task = new Issue()
        {
            Summary = "Implementar SCRUM-14",
            Description = "Integração com Jira para tracking de atividades em csharp.",
            Priority = "High",
            Status = "To Do"
        };

        // Adiciona a nova tarefa ao projeto
        await jiraClient.Issue.CreateAsync("your-project-key", task);

        Console.WriteLine("Tarefa criada com sucesso!");

        // Monitoramento de tarefas (exemplo: aguardar 5 segundos antes de sair)
        Task.Delay(5000).Wait();

        Console.WriteLine("Programa finalizado.");
    }
}