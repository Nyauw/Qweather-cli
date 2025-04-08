# jwt_token.py
import time
import jwt


def generate_qweather_token(private_key_path="ed25519-private.pem"):
    """
    自动生成和风天气JWT Token
    :param private_key_path: EdDSA私钥文件路径
    :return: 有效期为5分钟的JWT Token
    """
    try:
        # 读取私钥文件
        with open(private_key_path, "r") as pem_file:
            private_key = pem_file.read().strip()

        # 生成Payload
        payload = {
            'iat': int(time.time()) - 30,  # 补偿时间差
            'exp': int(time.time()) + 300,  # 5分钟有效期
            'sub': 'your_sub_id'  # 你的账户ID
        }

        # 请求头信息
        headers = {
            'kid': 'your_kid'  # 你的Key ID
        }

        # 生成Token
        return jwt.encode(
            payload,
            private_key,
            algorithm='EdDSA',
            headers=headers
        )

    except FileNotFoundError:
        print(f"❌ 私钥文件 {private_key_path} 未找到")
        exit(1)
    except jwt.PyJWTError as e:
        print(f"❌ JWT生成失败: {str(e)}")
        exit(1)


if __name__ == "__main__":
    # 单独测试Token生成
    print("生成的Token:", generate_qweather_token())