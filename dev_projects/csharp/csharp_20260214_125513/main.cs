using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        // Inicializa a conexão com o Jira
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Cria um novo issue no Jira
        var issue = new Issue()
        {
            Summary = "Teste do Agent",
            Description = "Este é um teste para o agent do JiraSharp.Client.",
            Priority = 3,
            Status = 1
        };

        // Inclui o issue no Jira
        await jiraClient.CreateIssueAsync(issue);

        Console.WriteLine("Issue criado com sucesso!");

        // Monitoramento de atividades (exemplo: listar todas as issues)
        var issues = await jiraClient.GetIssuesAsync();
        foreach (var i in issues)
        {
            Console.WriteLine($"ID: {i.Id}, Summary: {i.Summary}");
        }
    }
}