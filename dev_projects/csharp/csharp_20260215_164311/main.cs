using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do JiraSharp
        var jira = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        // Cria uma nova tarefa no Jira
        var task = await jira.CreateTaskAsync(new TaskCreateRequest
        {
            Summary = "Implementar C# Agent com Jira",
            Description = "Integrar C# Agent com Jira - tracking de atividades"
        });

        Console.WriteLine($"Tarefa criada: {task.Key}");
    }
}