using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

namespace CSharpAgentJiraIntegration
{
    public class Program
    {
        public static async Task Main(string[] args)
        {
            try
            {
                // Configuração do cliente Jira
                var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

                // Cria uma nova tarefa no Jira
                var task = new Task
                {
                    Summary = "Teste da Integração",
                    Description = "Integrando C# Agent com Jira",
                    Assignee = client.Users.Get("user-id"),
                    Priority = client.Priorities.Get("high")
                };

                // Adiciona a tarefa ao projeto
                var project = client.Projects.Get("project-id");
                await task.CreateAsync(project);

                Console.WriteLine("Tarefa criada com sucesso!");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Erro: {ex.Message}");
            }
        }
    }

    public class Task
    {
        public string Summary { get; set; }
        public string Description { get; set; }
        public User Assignee { get; set; }
        public Priority Priority { get; set; }

        public async Task CreateAsync(Project project)
        {
            var createTaskResult = await project.Tasks.CreateAsync(this);
            Console.WriteLine($"Tarefa criada com ID: {createTaskResult.Id}");
        }
    }

    public class User
    {
        public string Name { get; set; }
        public int Id { get; set; }

        public override string ToString()
        {
            return $"User: {Name} (ID: {Id})";
        }
    }

    public class Priority
    {
        public string Name { get; set; }
        public int Id { get; set; }

        public override string ToString()
        {
            return $"Priority: {Name} (ID: {Id})";
        }
    }
}