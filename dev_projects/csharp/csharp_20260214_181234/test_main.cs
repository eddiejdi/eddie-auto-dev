using System;
using System.Net.Http;
using System.Threading.Tasks;
using JiraSharp;

class ProgramTests
{
    [Fact]
    public async Task CreateTaskAsync_WithValidData_ReturnsTask()
    {
        var client = new HttpClient();
        var jiraClient = new JiraClient(client);

        var task = await jiraClient.CreateTaskAsync("My New Task", "This is a test task.");

        Assert.NotNull(task);
        Assert.NotEmpty(task.Id);
    }

    [Fact]
    public async Task CreateTaskAsync_WithInvalidData_ReturnsNull()
    {
        var client = new HttpClient();
        var jiraClient = new JiraClient(client);

        var task = await jiraClient.CreateTaskAsync("", "This is a test task.");

        Assert.Null(task);
    }

    [Fact]
    public async Task GetTaskAsync_WithValidData_ReturnsTaskDetails()
    {
        var client = new HttpClient();
        var jiraClient = new JiraClient(client);

        // Create a task first
        var task = await jiraClient.CreateTaskAsync("My New Task", "This is a test task.");

        if (task != null)
        {
            var taskDetails = await jiraClient.GetTaskAsync(task.Id);

            Assert.NotNull(taskDetails);
            Assert.NotEmpty(taskDetails.Id);
            Assert.Equal("Done", taskDetails.Status);
        }
    }

    [Fact]
    public async Task GetTaskAsync_WithInvalidData_ReturnsNull()
    {
        var client = new HttpClient();
        var jiraClient = new JiraClient(client);

        var taskDetails = await jiraClient.GetTaskAsync("invalidId");

        Assert.Null(taskDetails);
    }
}