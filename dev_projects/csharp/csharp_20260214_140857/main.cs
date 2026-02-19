using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharpClient;

class Program
{
    static async Task Main(string[] args)
    {
        try
        {
            // Configuração do cliente Jira
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Cria uma nova tarefa no Jira
            var task = new Task
            {
                Summary = "Implementar o C# Agent com Jira",
                Description = "Integrar C# Agent com Jira para tracking de atividades",
                Assignee = client.Users.Get("assignee-username"),
                Priority = client.Priorities.Get("high")
            };

            // Adiciona a tarefa ao projeto
            var project = client.Projects.Get("project-id");
            await task.Create(project);

            Console.WriteLine($"Tarefa criada com sucesso: {task.Key}");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Erro ao integrar C# Agent com Jira: {ex.Message}");
        }
    }
}