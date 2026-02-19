using System;
using System.Diagnostics;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        try
        {
            // Configuração do cliente Jira
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Tarefa a ser executada em background
            await ExecuteTask(client);

            Console.WriteLine("Tarefa executada com sucesso!");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Erro: {ex.Message}");
        }
    }

    static async Task ExecuteTask(JiraClient client)
    {
        // Simulação de tarefa que deve ser executada em background
        await Task.Delay(5000);

        try
        {
            // Criar uma nova tarefa no Jira
            var issue = new Issue
            {
                Summary = "Tarefa executada em background",
                Description = "Esta é uma tarefa simulada que deve ser executada em background.",
                ProjectKey = "YOUR_PROJECT_KEY"
            };

            await client.CreateIssueAsync(issue);

            Console.WriteLine("Tarefa criada no Jira com sucesso!");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Erro ao criar tarefa no Jira: {ex.Message}");
        }
    }
}