from github import Github, GithubException

import config


class GitHubClient:
    def __init__(self):
        g = Github(config.GITHUB_TOKEN)
        self._repo = g.get_repo(config.GITHUB_REPO)
        self._release = self._get_or_create_release()

    def _get_or_create_release(self):
        for release in self._repo.get_releases():
            if release.tag_name == config.GITHUB_RELEASE_TAG:
                return release
        return self._repo.create_git_release(
            tag=config.GITHUB_RELEASE_TAG,
            name="Podcast MP3 Files",
            message="Auto-generated MP3s from Gmail newsletters",
            draft=False,
            prerelease=False,
        )

    def upload_mp3(self, file_path: str, filename: str) -> str:
        owner, repo = config.GITHUB_REPO.split("/")
        url = (
            f"https://github.com/{owner}/{repo}"
            f"/releases/download/{config.GITHUB_RELEASE_TAG}/{filename}"
        )
        # Releaseを最新状態にリフレッシュ
        self._release = self._get_or_create_release()
        for asset in self._release.get_assets():
            if asset.name == filename:
                asset.delete_asset()
                break
        try:
            self._release.upload_asset(file_path, name=filename, content_type="audio/mpeg")
        except GithubException as e:
            if e.status == 422 and any(
                err.get("code") == "already_exists"
                for err in e.data.get("errors", [])
            ):
                print(f"  Asset already exists, reusing: {filename}")
            else:
                raise
        return url
