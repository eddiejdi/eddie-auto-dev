using System;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do JiraSharp Client
        var client = new JiraSharpClient("https://your-jira-instance.atlassian.net", "username", "password");

        // Cria um novo ticket
        var issue = new Issue()
        {
            Title = "Teste de C# Agent com Jira",
            Description = "Este é um teste para integrar o C# Agent com Jira.",
            ProjectKey = "YOUR_PROJECT_KEY"
        };

        try
        {
            // Cria o ticket no Jira
            var createdIssue = await client.CreateIssueAsync(issue);

            Console.WriteLine($"Ticket criado: {createdIssue.Key}");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Erro ao criar ticket: {ex.Message}");
        }

        // Fim do programa
    }
}