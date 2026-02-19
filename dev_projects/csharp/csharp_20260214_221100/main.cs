using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do cliente Jira
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        // Criar um projeto no Jira
        var project = await client.Projects.CreateAsync(new ProjectCreateRequest()
        {
            Key = "TEST",
            Name = "Test Project",
            Description = "This is a test project for integration with Jira."
        });

        Console.WriteLine($"Project created: {project.Key}");

        // Criar uma tarefa no Jira
        var issue = await client.Issues.CreateAsync(new IssueCreateRequest()
        {
            Key = "TEST-1",
            ProjectId = project.Id,
            Summary = "Test Task",
            Description = "This is a test task for integration with Jira."
        });

        Console.WriteLine($"Issue created: {issue.Key}");

        // Monitorar o progresso da tarefa
        while (true)
        {
            var issueStatus = await client.Issues.GetAsync(issue.Id);
            Console.WriteLine($"Issue status: {issueStatus.Fields.Status.Name}");

            if (issueStatus.Fields.Status.Name == "Done")
            {
                Console.WriteLine("Task completed!");
                break;
            }

            await Task.Delay(1000); // Esperar 1 segundo antes de verificar novamente
        }
    }
}