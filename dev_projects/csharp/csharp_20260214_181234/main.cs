using System;
using System.Net.Http;
using System.Threading.Tasks;
using JiraSharp;

class Program
{
    static async Task Main(string[] args)
    {
        var client = new HttpClient();
        var jiraClient = new JiraClient(client);

        // Crie uma nova tarefa no Jira
        var task = await jiraClient.CreateTaskAsync("My New Task", "This is a test task.");

        Console.WriteLine($"Task created: {task.Id}");

        // Monitorar a tarefa e notificar por email quando ela estiver concluída
        while (true)
        {
            var taskDetails = await jiraClient.GetTaskAsync(task.Id);
            if (taskDetails.Status == "Done")
            {
                Console.WriteLine($"Task completed: {taskDetails.Id}");
                // Notificar por email
                await SendEmail(jiraClient, taskDetails);
                break;
            }
            else
            {
                Console.WriteLine($"Task status: {taskDetails.Status}");
                await Task.Delay(60000); // Check every minute
            }
        }
    }

    static async Task SendEmail(JiraClient jiraClient, TaskDetails taskDetails)
    {
        var email = new Email()
        {
            To = "recipient@example.com",
            Subject = $"Task {taskDetails.Id} Completed",
            Body = $"The task {taskDetails.Id} has been completed."
        };

        await jiraClient.SendEmailAsync(email);
    }
}