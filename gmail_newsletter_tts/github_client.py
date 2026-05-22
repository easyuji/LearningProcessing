from github import Github, GithubException

import config


class GitHubClient:
    def __init__(self):
        g = Github(config.GITHUB_TOKEN)
        self._repo = g.get_repo(config.GITHUB_REPO)
        self._release = self._get_or_create_release()

    def _get_or_create_release(self):
        try:
            return self._repo.get_release(config.GITHUB_RELEASE_TAG)
        except GithubException:
            return self._repo.create_git_release(
                tag=config.GITHUB_RELEASE_TAG,
                name="Podcast MP3 Files",
                message="Auto-generated MP3s from Gmail newsletters",
                draft=False,
                prerelease=False,
            )

    def upload_mp3(self, file_path: str, filename: str) -> str:
        for asset in self._release.get_assets():
            if asset.name == filename:
                asset.delete_asset()
                break
        self._release.upload_asset(file_path, name=filename, content_type="audio/mpeg")
        owner, repo = config.GITHUB_REPO.split("/")
        return (
            f"https://github.com/{owner}/{repo}"
            f"/releases/download/{config.GITHUB_RELEASE_TAG}/{filename}"
        )
